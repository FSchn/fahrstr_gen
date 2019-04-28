#!/usr/bin/env python3

import unittest
import os
import subprocess
import sys
import re

class TestFahrstrGen(unittest.TestCase):
    def run_fahrstr_gen(self, st3, args=[]):  # return: (retcode, output)
        env = os.environ.copy()
        env["ZUSI3_DATAPATH"] = os.getcwd()
        cmd = [sys.executable, '../fahrstr_gen.py', '--modus=vergleiche'] + args + [f"./routes/{st3}"]
        print(f'''ZUSI3_DATAPATH="{env["ZUSI3_DATAPATH"]}" {'"' + '" "'.join(cmd) + '"'}''')
        with subprocess.Popen(cmd, stderr=subprocess.PIPE, text='utf-8', env=env) as child:
            stdout, stderr = child.communicate()
        print(stderr)
        return (child.returncode, stderr)

    def get_vergleich_resultat(self, stderr):
        r = re.compile('[0-9]+:INFO:(.*)')
        result = set()
        vergleich_aktiv = False
        for line in stderr.splitlines():
            m = r.match(line)
            if m is not None:
                if m.group(1) == "Vergleiche erzeugte Fahrstrassen mit denen aus der ST3-Datei.":
                    vergleich_aktiv = True
                elif m.group(1) == "Fahrstrassen-Vergleich abgeschlossen.":
                    vergleich_aktiv = False
                elif vergleich_aktiv:
                    result.add(m.group(1))
        return result

    def get_warnungen(self, stderr):
        r = re.compile('[0-9]+:WARNING:(.*)')
        result = set()
        for line in stderr.splitlines():
            m = r.match(line)
            if m is not None:
                result.add(m.group(1))
        return result

    # ---

    def test_rangiersignal(self):
        (retcode, stderr) = self.run_fahrstr_gen("RangiersignalTest.st3")
        self.assertEqual(retcode, 2)
        self.assertSetEqual(self.get_vergleich_resultat(stderr), set([
            "Anfang A -> Mitte M: Hauptsignalverknuepfung (RANGIERSIGNALTEST.ST3,7) (Signal Mitte M an Element 5b) ist in Zusi vorhanden, wurde aber nicht erzeugt",
            "Mitte M -> Ende E: Hauptsignalverknuepfung (RANGIERSIGNALTEST.ST3,7) (Signal Mitte M an Element 5b) hat unterschiedliche Zeile: (-1, True) vs. (0, True)",
            ]))

    def test_fahrstr_nummerierung(self):
        (retcode, stderr) = self.run_fahrstr_gen("FahrstrNummerierungTest.st3", ["--fahrstr_typen", "rangier,zug"])
        self.assertEqual(retcode, 2)
        self.assertSetEqual(self.get_vergleich_resultat(stderr), set([
            "Fahrstrasse Anfang A -> Mitte M -> Ende E (1) (TypRangier) existiert in Zusi, wurde aber nicht erzeugt",
            ]))

    def test_ungueltige_richtungsanzeiger(self):
        (retcode, stderr) = self.run_fahrstr_gen("UngueltigeRichtungsanzeigerTest.st3")
        self.assertEqual(retcode, 0)
        self.assertSetEqual(self.get_warnungen(stderr), set([
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Richtungsanzeiger-Ziel" ohne Text',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Richtungsanzeiger-Ziel" mit Signalbegriff-Nr. -3, die nicht im Bereich 0..63 liegt',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Richtungsanzeiger-Ziel" mit Signalbegriff-Nr. 64, die nicht im Bereich 0..63 liegt',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Richtungsvoranzeiger" ohne Text',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Richtungsvoranzeiger" mit Signalbegriff-Nr. -3, die nicht im Bereich 0..63 liegt',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Richtungsvoranzeiger" mit Signalbegriff-Nr. 64, die nicht im Bereich 0..63 liegt',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Gegengleis kennzeichnen" mit Signalbegriff-Nr. -3, die nicht im Bereich 0..63 liegt',
            'Signal Anfang A an Element 1g: Matrix enthaelt Ereignis "Gegengleis kennzeichnen" mit Signalbegriff-Nr. 64, die nicht im Bereich 0..63 liegt',
            ]))

    def test_fahrstr_start_ziel_signal_test(self):
        (retcode, stderr) = self.run_fahrstr_gen("FahrstrStartZielSignalTest.st3")
        self.assertEqual(retcode, 0)

    def test_register_verkn_ungueltiges_modul(self):
        (retcode, stderr) = self.run_fahrstr_gen("RegisterVerknuepfungUngueltigesModul.st3")
        self.assertEqual(retcode, 0)

    def test_alternative_fahrwege_bahnsteigkreuzung(self):
        (retcode, stderr) = self.run_fahrstr_gen("AlternativeFahrwegeBahnsteigkreuzung.st3", ["--alternative_fahrwege"])
        self.assertEqual(retcode, 0)

    def test_signalgeschwindigkeit_anzeigegefuehrt(self):
        (retcode, stderr) = self.run_fahrstr_gen("SignalgeschwindigkeitAnzeigegefuehrt.st3")
        self.assertEqual(retcode, 0)

    def test_fahrstr_laenge(self):
        (retcode, stderr) = self.run_fahrstr_gen("FahrstrLaengeTest.st3")
        self.assertEqual(retcode, 0)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFahrstrGen)
    unittest.TextTestRunner(verbosity=2).run(suite)
