"""Umwelt- und Signalmodell des BioComm-Sandkastens (frei gewaehlte Demo-Annahmen).

Alles ist deterministisch: gleiche Seeds -> identische Werte (Reproduzierbarkeit,
Spezifikation v7 4.2). Zeiten sind Sekunden ab Beginn der Jahresachse (UTC).

Kein Anspruch auf biologische Richtigkeit. Die Formeln sollen nur plausible
Groessenordnungen, Tages-/Jahresgaenge und Stoerungen liefern, damit Dashboard,
Aggregation und Datenqualitaet realistisch getestet werden koennen.
"""
import bisect
import math
import random
from datetime import timedelta
from zoneinfo import ZoneInfo

from omn.sandbox.szenarien import EC_DAUER_S, EC_EINSCHWING_S, GAIN, LSB_UV, RATE_HZ

# groesster darstellbarer Wert des ADC (int16) in uV am Eingang -> Saettigung
SAETTIGUNG_UV = 32767 * LSB_UV / GAIN
EC_PAUSE_S = EC_DAUER_S + EC_EINSCHWING_S


def _begrenzt(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _poisson(rng, lam):
    """Knuth -- fuer die hier vorkommenden kleinen lambda voellig ausreichend."""
    grenze, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= grenze:
            return k
        k += 1


class Abdeckung:
    """Wann die Aufzeichnung (Gerätezeit) tatsaechlich lief: Runs minus Luecken
    minus uebersprungene Zeit (Uhr-Vorwaertssprung). EC-Pausen des Bio-Kanals
    kommen stuendlich hinzu (hh:00:00 bis hh:00:35) und werden getrennt behandelt."""

    def __init__(self, intervalle):
        self.iv = sorted(intervalle)
        self._starts = [a for a, _ in self.iv]

    def schnitt(self, a, b):
        """Teilintervalle von [a, b), in denen aufgezeichnet wurde."""
        out = []
        i = max(0, bisect.bisect_right(self._starts, a) - 1)
        while i < len(self.iv) and self.iv[i][0] < b:
            x, y = max(a, self.iv[i][0]), min(b, self.iv[i][1])
            if y > x:
                out.append((x, y))
            i += 1
        return out

    def enthaelt(self, t):
        return bool(self.schnitt(t, t + 1e-6))

    @staticmethod
    def ohne_ec(teile):
        """Bio-Kanal: EC-Messfenster (hh:00:00 bis hh:00:35) herausschneiden."""
        out = []
        for x, y in teile:
            h = math.floor(x / 3600)
            while h * 3600 < y:
                p0, p1 = h * 3600, h * 3600 + EC_PAUSE_S
                if p1 <= x or p0 >= y:
                    pass
                else:
                    if x < p0:
                        out.append((x, p0))
                    x = max(x, p1)
                h += 1
            if y > x:
                out.append((x, y))
        return [(a, b) for a, b in out if b > a]


class Umwelt:
    """Stuendliche Umweltgroessen fuer einen Standort, dazwischen linear."""

    def __init__(self, standort, seed, start_utc, stunden):
        self.s = standort
        self.start = start_utc
        self.n = stunden + 2
        rng = random.Random(seed * 7 + 11)
        zone = ZoneInfo(standort.iana_tz)
        sued = standort.breite < 0
        spitze = 22 if sued else 205                     # waermster Tag im Jahr
        self.boden, self.luft, self.feuchte, self.relf = [], [], [], []
        self.co2, self.ec, self.soc, self.volt, self.akt, self.lokal_h = [], [], [], [], [], []
        m = standort.feuchte_basis
        rausch_b = rausch_l = 0.0
        soc = 100.0
        for h in range(self.n):
            t = start_utc + timedelta(hours=h)
            lok = t.astimezone(zone)
            lh = lok.hour + lok.minute / 60
            doy = lok.timetuple().tm_yday
            jahr = math.cos(2 * math.pi * (doy - spitze) / 365.0)
            tag = math.sin(2 * math.pi * (lh - 9) / 24)
            rausch_b = 0.97 * rausch_b + rng.gauss(0, 0.12)
            rausch_l = 0.9 * rausch_l + rng.gauss(0, 0.5)
            boden = s_b = standort.boden_mittel + standort.boden_amplitude * jahr + 0.9 * tag + rausch_b
            luft = standort.luft_mittel + standort.luft_amplitude * jahr + 5.0 * tag + rausch_l
            if lok.hour == 6 and rng.random() < standort.regen_wahrscheinlichkeit:
                m += rng.uniform(3, 12)                   # Regen am Morgen
            m += (standort.feuchte_basis + 4 * jahr * (-1 if standort.boden_amplitude > 3 else 0) - m) / 120
            m -= max(0.0, luft - 15) * 0.004             # Verdunstung
            m = _begrenzt(m, 6.0, 45.0)
            relf = _begrenzt(72 - 2.2 * (luft - standort.luft_mittel) + 0.6 * (m - standort.feuchte_basis)
                             + rng.gauss(0, 2), 20, 100)
            akt = _begrenzt((s_b - 2) / 16, 0, 1) * _begrenzt((m - 8) / 22, 0, 1)
            soc -= 100 / (45 * 24)                       # Akku reicht ca. 45 Tage
            if soc < 15:
                soc = 100.0                              # Akkutausch
            self.boden.append(boden)
            self.luft.append(luft)
            self.feuchte.append(m)
            self.relf.append(relf)
            self.co2.append(415 + 140 * akt + 30 * max(0.0, -tag) + rng.gauss(0, 6))
            self.ec.append(max(0.05, 0.12 + 0.018 * m + 0.006 * max(boden, 0) + rng.gauss(0, 0.01)))
            self.soc.append(soc)
            self.volt.append(3.45 + 0.75 * soc / 100 + rng.gauss(0, 0.005))
            self.akt.append(akt)
            self.lokal_h.append(lh)

    def _interp(self, reihe, t):
        x = t / 3600
        i = min(max(int(x), 0), self.n - 2)
        f = x - i
        return reihe[i] * (1 - f) + reihe[i + 1] * f

    def aktivitaet(self, t):
        return self._interp(self.akt, t)

    def lokale_stunde(self, t):
        i = min(max(int(t / 3600), 0), self.n - 1)
        return (self.lokal_h[i] + (t / 3600 - int(t / 3600))) % 24

    def wert(self, groesse, t):
        reihe = {
            'soil_temperature': self.boden, 'soil_moisture': self.feuchte,
            'electrical_conductivity': self.ec, 'air_temperature': self.luft,
            'relative_humidity': self.relf, 'co2': self.co2,
            'battery_voltage': self.volt, 'battery_state_of_charge': self.soc,
        }[groesse]
        return self._interp(reihe, t)


class Reaktion:
    """Angenommene, abklingende Reaktion nach einer ausgefuehrten Stimulation
    (ARBITRARY_DEMO). Nur in der Stimulationsreihe, nie in der Kontrollreihe."""
    TAU_S = 600.0
    DAUER_S = 3600.0

    def __init__(self, ende_s, amplitude_uv, rng):
        self.ende = ende_s
        self.a = amplitude_uv
        # ein paar zusaetzliche Spikes in den 20 Minuten danach
        self.spikes = [(ende_s + rng.uniform(0, 1200), rng.choice((-1, 1)) * rng.uniform(60, 220))
                       for _ in range(_poisson(rng, 3 + amplitude_uv / 8))]

    def wert(self, t):
        d = t - self.ende
        return self.a * math.exp(-d / self.TAU_S) if 0 <= d < self.DAUER_S else 0.0


class Bio:
    """PRIMARY-Kanal (bioelektrisches Potential, uV am Eingang)."""

    def __init__(self, umwelt, seed, stunden, reaktionen=(), stoerungen=()):
        self.u = umwelt
        self.seed = seed
        rng = random.Random(seed)
        self.drift, self.sigma = [], []
        d = 0.0
        for h in range(stunden + 2):
            d += rng.gauss(0, 3.0) - 0.02 * d            # begrenzte Zufallsdrift
            self.drift.append(d)
            self.sigma.append(4.0 + 18.0 * umwelt.akt[min(h, umwelt.n - 1)])
        self.reaktionen = sorted(reaktionen, key=lambda r: r.ende)
        self._r_enden = [r.ende for r in self.reaktionen]
        self.stoerungen = list(stoerungen)               # [(von_s, bis_s, offset_uv)]
        self._spike_cache = {}

    # -- Bausteine ----------------------------------------------------------
    def _reaktion(self, t):
        i = bisect.bisect_right(self._r_enden, t)
        w = 0.0
        while i > 0 and t - self._r_enden[i - 1] < Reaktion.DAUER_S:
            w += self.reaktionen[i - 1].wert(t)
            i -= 1
        return w

    def _stoerung(self, t):
        return sum(o for a, b, o in self.stoerungen if a <= t < b)

    def mittel(self, t):
        """Erwartungswert ohne Rauschen und Spikes."""
        a = self.u.aktivitaet(t)
        x = t / 3600
        i = min(int(x), len(self.drift) - 2)
        f = x - i
        drift = self.drift[i] * (1 - f) + self.drift[i + 1] * f
        tag = 15.0 * a * math.sin(2 * math.pi * (self.u.lokale_stunde(t) - 14) / 24)
        return drift + tag + self._reaktion(t) + self._stoerung(t)

    def sigma_bei(self, t):
        return self.sigma[min(int(t / 3600), len(self.sigma) - 1)]

    def spikes_stunde(self, h):
        """Spontane Spikes der Stunde h (deterministisch je Stunde) + Reaktions-Spikes."""
        if h in self._spike_cache:
            return self._spike_cache[h]
        rng = random.Random(self.seed * 1_000_003 + h)
        a = self.u.akt[min(h, self.u.n - 1)]
        sp = [(h * 3600 + rng.uniform(0, 3600), rng.choice((-1, 1)) * rng.uniform(40, 200) * (0.5 + a))
              for _ in range(_poisson(rng, 3 + 25 * a))]
        for r in self.reaktionen:
            sp.extend(s for s in r.spikes if h * 3600 <= s[0] < (h + 1) * 3600)
        sp.sort()
        self._spike_cache[h] = sp
        if len(self._spike_cache) > 5000:
            self._spike_cache.clear()
        return sp

    # -- Aggregate aus dem Modell (ausserhalb der Rohdatenstunden) ----------
    def aggregat(self, teile, k_sigma):
        """(Anzahl Samples, min, max, mittel) ueber die Teilintervalle, oder None."""
        n = sum(b - a for a, b in teile) * RATE_HZ
        if n <= 0:
            return None
        summe = gewicht = 0.0
        lo, hi = math.inf, -math.inf
        for a, b in teile:
            schritte = max(1, int((b - a) // 60))
            dt = (b - a) / schritte
            for j in range(schritte):
                t = a + (j + 0.5) * dt
                m = self.mittel(t)
                s = self.sigma_bei(t)
                summe += m * dt
                gewicht += dt
                lo = min(lo, m - k_sigma * s)
                hi = max(hi, m + k_sigma * s)
            for ts, amp in self.spikes_stunde(int(a // 3600)):
                if a <= ts < b:
                    spitze = self.mittel(ts) + amp
                    lo, hi = min(lo, spitze), max(hi, spitze)
        lo = max(lo, -SAETTIGUNG_UV)
        hi = min(hi, SAETTIGUNG_UV)
        return round(n), lo, hi, _begrenzt(summe / gewicht, -SAETTIGUNG_UV, SAETTIGUNG_UV)

    # -- echte Rohdaten ------------------------------------------------------
    def roh(self, a, b):
        """Samples (ADC-Counts, int16, auf den Wertebereich begrenzt -> Saettigung)
        fuer [a, b) mit 250 Hz."""
        rng = random.Random(self.seed * 7_919 + int(a))
        n = round((b - a) * RATE_HZ)
        werte = [0.0] * n
        basis = {}
        for i in range(n):
            t = a + i / RATE_HZ
            sek = int(t)
            if sek not in basis:
                basis[sek] = (self.mittel(sek + 0.5), self.sigma_bei(sek))
            m, s = basis[sek]
            werte[i] = m + rng.gauss(0, s)
        # Spikes: schneller Anstieg, Abklingen ca. 50 ms
        for h in range(int(a // 3600), int((b - 1e-9) // 3600) + 1):
            for ts, amp in self.spikes_stunde(h):
                if a <= ts < b:
                    i0 = int((ts - a) * RATE_HZ)
                    for k in range(min(60, n - i0)):
                        werte[i0 + k] += amp * math.exp(-k / (0.05 * RATE_HZ))
        faktor = GAIN / LSB_UV
        return [int(_begrenzt(round(v * faktor), -32768, 32767)) for v in werte]
