import random
from math import ceil
from copy import deepcopy
from itertools import combinations
from collections import defaultdict

from l7r.dice import d10, prob, xky, avg


messages = []


def log(message):
    messages.append(message)
    print(messages[-1])


def all_subsets(xs):
    all = []
    for i in range(1, len(xs) + 1):
        all.extend(combinations(xs, i))
    return all


class Combatant:
    counts = defaultdict(int)

    sw_parry_threshold = 2
    sw2vp_threshold = 0.5
    vp_fail_threshold = 0.7
    datt_threshold = 0.20
    base_wc_threshold = 10

    hold_one_action = True
    base_damage_rolled = 4
    base_damage_kept = 2
    extra_vps = 0
    extra_serious = 0

    rank = 0
    school_knacks = []
    r1t_rolls = []
    r2t_rolls = None

    interrupt = ''

    def __init__(self, **kwargs):
        for knack in ['double_attack', 'feint', 'iaijutsu', 'lunge']:
            setattr(self, knack, 0)

        self.left = self.right = None
        self.crippled = self.dead = False
        self.light = self.serious = 0
        self.events = defaultdict(list)
        self.multi = defaultdict(list)
        self.attackable = set()
        self.extra_dice = defaultdict(lambda: [0, 0])
        self.disc = defaultdict(list)
        self.always = defaultdict(int)
        self.auto_once = defaultdict(int)

        self.counts[self.__class__] += 1
        self.name = self.__class__.__name__ + str(self.counts[self.__class__])

        self.__dict__.update(kwargs)

        self.reset_tn()
        self.vps = self.extra_vps + min([self.air, self.earth, self.fire, self.water, self.void])

        self.events['pre_attack'].append(self.lunge_pre_trigger)
        self.events['pre_attack'].append(self.lunge_succ_trigger)
        self.events['successful_attack'].append(self.feint_trigger)
        self.events['pre_attack'].append(self.datt_pre_trigger)
        self.events['post_attack'].append(self.datt_post_trigger)
        self.events['post_attack'].append(self.reset_damage)
        self.events['successful_attack'].append(self.datt_succ_trigger)

        if self.rank:
            for knack in self.school_knacks:
                setattr(self, knack, self.rank)
        elif self.school_knacks:
            self.rank = min(getattr(self, knack) for knack in self.school_knacks)

        for roll_type in self.r1t_rolls:
            self.extra_dice[roll_type][0] += 1
        if self.r2t_rolls:
            self.always[self.r2t_rolls] += 5

    def __getstate__(self):
        d = self.__dict__.copy()
        del d['events']
        return d

    def triggers(self, event, *args, **kwargs):
        to_remove = [f for f in self.events[event] if f(*args, **kwargs)]
        for f in to_remove:
            self.events[event].remove(f)

    def reset_tn(self):
        self.tn = 5 + 5 * self.parry
        return True

    def reset_damage(self):
        for bonus in ['damage_rolled', 'damage_kept', 'damage']:
            self.auto_once[bonus] = 0

    def datt_succ_trigger(self):
        if self.attack_knack == 'double_attack':
            self.auto_once['serious'] += 1
            self.auto_once['damage_rolled'] += 4

    def datt_pre_trigger(self):
        if self.attack_knack == 'double_attack':
            self.enemy.tn += 20

    def datt_post_trigger(self):
        if self.attack_knack == 'double_attack':
            self.enemy.tn -= 20

    def feint_trigger(self):
        if self.attack_knack == 'feint' and len(self.actions):
            self.vps += 1
            self.actions.pop()
            self.actions.insert(0, self.phase)

    def lunge_pre_trigger(self):
        if self.attack_knack == 'lunge':
            self.tn -= 5
            self.event['post_defense'].append(self.reset_tn)

    def lunge_succ_trigger(self):
        if self.attack_knack == 'lunge':
            self.auto_once['damage_rolled'] += 1

    def log(self, message, *, indent=4):
        log(' ' * indent + self.name + ': ' + message)

    def xky(self, roll, keep, reroll, roll_type):
        return xky(roll, keep, reroll)

    @property
    def spendable_vps(self):
        return range(self.vps + 1)

    @property
    def wc_threshold(self):
        return self.base_wc_threshold

    @property
    def sw_to_cripple(self):
        return self.earth

    @property
    def sw_to_kill(self):
        return self.extra_serious + 2 * self.earth

    @property
    def adjacent(self):
        adj = [self.left, self.right]
        return [a for a in adj if a]

    def use_disc_bonuses(self, roll_type, bonuses):
        all = [self.disc[roll_type]] + self.multi[roll_type]
        for bonus in bonuses:
            for bonus_group in all:
                if bonus in bonus_group:
                    bonus_group.remove(bonus)
                    break

    def disc_bonuses(self, roll_type):
        all = deepcopy(self.disc[roll_type])
        for bonuses in self.multi[roll_type]:
            all.extend(bonuses)
        return all

    def disc_bonus(self, roll_type, needed):
        if not needed:
            return 0

        bonuses = self.disc_bonuses(roll_type)
        all = [(sum(sub), sub) for sub in all_subsets(bonuses)]
        enough = [e for e in all if e[0] >= needed]
        best = min(enough)[1] if enough else []
        self.use_disc_bonuses(roll_type, best)
        return sum(best)

    def max_bonus(self, roll_type):
        return self.always[roll_type] + self.auto_once[roll_type] + sum(self.disc_bonuses(roll_type))

    def auto_once_bonus(self, roll_type):
        bonus = self.auto_once[roll_type]
        self.auto_once[roll_type] = 0
        return bonus

    def choose_action(self):
        if self.actions and self.actions[0] <= self.phase and (self.phase == 10 or not self.hold_one_action or len(self.actions) >= 2 and self.actions[1] <= self.phase):
            self.actions.pop(0)
            knack = 'attack'

            if self.double_attack:
                tn = min(e.tn for e in self.attackable)
                datt_prob = self.att_prob('double_attack', tn + 20)
                att_prob = self.att_prob('attack', tn)
                if att_prob - datt_prob <= self.datt_threshold:
                    knack = 'double_attack'

            return knack, self.att_target(knack)

    def will_counterattack(self, enemy):
        return False

    def will_counterattack_for(self, ally, enemy):
        return False

    @property
    def init_dice(self):
        roll, keep = self.extra_dice['initiative']
        roll += self.void + 1
        keep += self.void
        return roll, keep

    def initiative(self):
        roll, keep = self.init_dice
        self.actions = sorted(d10(False) for i in range(roll))[:keep]
        self.init_order = self.actions[:]
        self.log(f'initiative: {self.actions}', indent=0)

    @property
    def damage_dice(self):
        roll, keep = self.extra_dice['damage']
        roll += self.base_damage_rolled + self.fire
        keep += self.base_damage_kept
        return roll, keep

    def next_damage(self, tn, extra_damage):
        extra_rolled = max(0, self.attack_roll - tn) // 5 + self.auto_once_bonus('damage_rolled')
        extra_kept = self.auto_once_bonus('damage_kept')
        extra_serious = self.auto_once_bonus('serious')

        roll, keep = self.damage_dice
        if extra_damage:
            roll += extra_rolled
            keep += extra_kept

        return roll, keep, (extra_serious if extra_damage else 0)

    def deal_damage(self, tn, extra_damage=True):
        roll, keep, serious = self.next_damage(tn, extra_damage)
        self.last_damage_rolled = roll
        light = self.xky(roll, keep, True, 'damage') + self.auto_once_bonus('damage')
        self.log(f'deals {light} light and {serious} serious wounds')
        return light, serious

    @property
    def wc_dice(self):
        roll, keep = self.extra_dice['wound_check']
        roll += self.water + 1
        keep += self.water
        return roll, keep

    def calc_serious(self, light, check):
        return int(ceil(max(0, light - check) / 10))

    def avg_serious(self, light, roll, keep):
        wounds = []
        for vps in self.spendable_vps:
            avg_wc = avg(True, roll + vps, keep + vps) + self.max_bonus('wound_check')
            wounds.append([vps, self.calc_serious(light, avg_wc)])
        return wounds

    def wc_bonus(self, light, check):
        bonus = self.always['wound_check'] + self.auto_once_bonus('wound_check')
        if self.serious + 1 == self.sw_to_kill:
            needed = max(0, light - check - bonus)
            return bonus + self.disc_bonus('wound_check', needed)
        else:
            needed = max(0, light - check - bonus - 9)
            while needed > sum(self.disc_bonuses('wound_check')):
                needed = max(0, needed - 10)
            return bonus + self.disc_bonus('wound_check', needed)

    def wc_vps(self, light, roll, keep):
        wounds = self.avg_serious(light, roll, keep)
        for i in range(len(wounds) - 1, 0, -1):
            vps, serious = wounds[i]
            if serious < wounds[i - 1][1] and (
                    self.sw2vp_threshold <= (wounds[0][1] - serious) / vps
                    or serious + self.serious >= self.sw_to_kill):
                self.triggers('vps_spent', vps, 'wound_check')
                self.vps -= vps
                return vps
        return 0

    def wound_check(self, light, serious=0):
        light_total = light + self.light
        prev_serious = self.serious
        self.serious += serious

        roll, keep = self.wc_dice
        vps = self.wc_vps(light_total, roll, keep)
        check = self.xky(roll + vps, keep + vps, True, 'wound_check')
        check += self.wc_bonus(light_total, check)

        self.triggers('wound_check', check, light, light_total)
        if check < light_total:
            self.light = 0
            self.serious += self.calc_serious(light_total, check)
        elif light_total <= self.wc_threshold or self.serious >= self.sw_to_kill - 1:
            self.light = light_total
        else:
            self.light = 0
            self.serious += 1

        self.log(f'{check} wound check ({vps} vp) vs {light_total} light wounds, takes {self.serious - prev_serious} serious')
        self.crippled = self.serious >= self.sw_to_cripple
        self.dead = self.serious >= self.sw_to_kill

    def att_dice(self, knack):
        roll, keep = self.extra_dice[knack]
        roll += self.fire + getattr(self, knack)
        keep += self.fire
        return roll, keep

    def att_prob(self, knack, tn):
        roll, keep = self.att_dice(knack)
        return prob[not self.crippled][roll, keep, tn - self.max_bonus(knack)]

    def att_target(self, knack='attack'):
        min_tn = min(e.tn for e in self.attackable)
        targets = [e for e in self.attackable if knack != 'double_attack' or e.tn == min_tn]
        return random.choice(sum([[e] * (1 + e.serious + (30 - e.tn) // 5 + len(e.init_order) - len(e.actions)) for e in targets], []))

    def att_bonus(self, tn, attack_roll):
        bonus = self.always[self.attack_knack] + self.auto_once_bonus(self.attack_knack)
        needed = max(0, tn - attack_roll - bonus)
        return bonus + self.disc_bonus(self.attack_knack, needed)

    def att_vps(self, tn, roll, keep):
        max_bonus = self.max_bonus(self.attack_knack)
        for vps in self.spendable_vps:
            if prob[self.crippled][roll + vps, keep + vps, tn - max_bonus] >= self.vp_fail_threshold:
                self.triggers('vps_spent', vps, self.attack_knack)
                self.vps -= vps
                return vps
        return 0

    def make_attack(self):
        roll, keep = self.att_dice(self.attack_knack)
        vps = self.att_vps(self.enemy.tn, roll, keep)
        result = self.xky(roll + vps, keep + vps, not self.crippled, self.attack_knack)
        self.attack_roll = result + self.att_bonus(self.enemy.tn, result)
        self.log(f'{self.attack_roll} {self.attack_knack} roll ({vps} vp) vs {self.enemy.tn} tn')

        success = self.attack_roll >= self.enemy.tn
        if success:
            self.triggers('successful_attack')
        return success and self.attack_knack != 'feint'

    @property
    def parry_dice(self):
        roll, keep = self.extra_dice['parry']
        roll += self.air + self.parry
        keep += self.air
        return roll, keep

    def will_predeclare(self):
        self.predeclare_bonus = 0
        return False

    def projected_damage(self, enemy, extra_damage):
        droll, dkeep, serious = deepcopy(enemy).next_damage(self.tn, extra_damage)
        light = avg(True, droll, dkeep)
        wcroll, wckeep = self.wc_dice
        return serious + self.avg_serious(light, wcroll, wckeep)[0][1]

    def will_parry(self):
        extra = self.projected_damage(self.enemy, True)
        base = self.projected_damage(self.enemy, False)

        self.interrupt = ''
        if self.predeclare_bonus:
            parry = True
        elif not self.actions or self.actions[0] > self.phase and len(self.actions) < 2:
            parry = False
        elif self.actions[0] > self.phase:
            parry = extra + self.serious >= self.sw_to_kill or extra - base >= 2 * self.sw_parry_threshold
            if parry:
                self.interrupt = 'interrupt '
                self.actions[-2:] = []
        else:
            parry = extra + self.serious >= self.sw_to_kill or extra - base >= self.sw_parry_threshold
            if parry:
                self.actions.pop(0)

        return parry

    def will_predeclare_for(self, ally, enemy):
        self.predeclare_bonus = 0
        return False

    def will_parry_for(self, ally, enemy):
        return False

    def parry_bonus(self, tn, parry_roll):
        bonus = self.predeclare_bonus + self.always['parry'] + self.auto_once_bonus('parry')
        self.predeclare_bonus = 0
        needed = max(0, tn - parry_roll - bonus)
        return bonus + self.disc_bonus('parry', needed)

    def parry_vps(self, tn, roll, keep):
        max_bonus = self.max_bonus('parry') + self.predeclare_bonus
        for vps in self.spendable_vps:
            if prob[self.crippled][roll + vps, keep + vps, tn - max_bonus] >= self.vp_fail_threshold:
                self.triggers('vps_spent', vps, 'parry')
                self.vps -= vps
                return vps
        return 0

    def make_parry_for(self, ally, enemy):
        enemy.attack_roll += 5 * getattr(enemy, enemy.attack_knack)
        success = self.make_parry(enemy)
        enemy.attack_roll -= 5 * getattr(enemy, enemy.attack_knack)
        return success

    def make_parry(self, auto_success=False):
        roll, keep = self.parry_dice
        vps = self.parry_vps(self.enemy.attack_roll, roll, keep)
        result = self.xky(roll + vps, keep + vps, not self.crippled, 'parry')
        self.parry_roll = result + self.parry_bonus(self.enemy.attack_roll, result)
        self.log(f'{self.parry_roll} {self.interrupt}parry roll ({vps} vp)')

        success = auto_success or self.parry_roll >= self.enemy.attack_roll
        if success:
            self.triggers('successful_parry')
        return success
