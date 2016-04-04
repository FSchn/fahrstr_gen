#!/usr/bin/env python3

from fahrstr_gen import modulverwaltung, streckengraph, strecke
from fahrstr_gen.konstanten import *
from fahrstr_gen.strecke import writeuglyxml, ist_hsig_fuer_fahrstr_typ, Element

import xml.etree.ElementTree as ET
import argparse
import operator
import tempfile
import shutil
import os
from collections import defaultdict

import logging

def refpunkt_fmt(refpunkt):
    pfad = refpunkt[1]
    if pfad.rfind('\\') != -1:
        pfad = pfad[pfad.rfind('\\')+1:]
    return "({},{})".format(pfad, refpunkt[0])

def finde_fahrstrassen(args):
    dieses_modul_relpath = modulverwaltung.get_zusi_relpath(args.dateiname)
    modulverwaltung.dieses_modul = modulverwaltung.Modul(dieses_modul_relpath.replace('/', '\\'), ET.parse(args.dateiname).getroot())
    modulverwaltung.module[modulverwaltung.normalize_zusi_relpath(dieses_modul_relpath)] = modulverwaltung.dieses_modul

    loeschfahrstrassen_namen = [n.get("FahrstrName", "") for n in modulverwaltung.dieses_modul.root.findall("./Strecke/LoeschFahrstrasse")]

    fahrstrassen = []
    fahrstrassen_nummerierung = defaultdict(list) # (Start-Refpunkt, ZielRefpunkt) -> [Fahrstrasse], zwecks Durchnummerierung

    vorsignal_graph = streckengraph.Streckengraph(FAHRSTR_TYP_VORSIGNALE)
    for fahrstr_typ in [FAHRSTR_TYP_ZUG, FAHRSTR_TYP_LZB]:
        logging.debug("Generiere Fahrstrassen vom Typ {}".format(fahrstr_typ))
        if fahrstr_typ in [FAHRSTR_TYP_ZUG, FAHRSTR_TYP_LZB]:
            graph = streckengraph.Streckengraph(fahrstr_typ, vorsignal_graph)
        else:
            graph = streckengraph.Streckengraph(fahrstr_typ)

        for nr, str_element in sorted(modulverwaltung.dieses_modul.streckenelemente.items(), key = lambda t: t[0]):
            if str_element in modulverwaltung.dieses_modul.referenzpunkte:
                for richtung in [NORM, GEGEN]:
                    if any(
                            (fahrstr_typ == FAHRSTR_TYP_ZUG and r.reftyp == REFTYP_AUFGLEISPUNKT)
                            or (r.reftyp == REFTYP_SIGNAL and ist_hsig_fuer_fahrstr_typ(r.signal(), fahrstr_typ))
                            for r in modulverwaltung.dieses_modul.referenzpunkte[str_element] if r.element_richtung.richtung == richtung
                        ):

                        for f in graph.get_knoten(str_element).get_fahrstrassen(richtung):
                            if f.name in loeschfahrstrassen_namen:
                                logging.info("Loesche Fahrstrasse: {}".format(f.name))
                            else:
                                if args.nummerieren:
                                    idx = len(fahrstrassen_nummerierung[(f.start, f.ziel)])
                                    if idx != 0:
                                        f.name += " ({})".format(idx)
                                    fahrstrassen_nummerierung[(f.start, f.ziel)].append(f)
                                fahrstrassen.append(f)

    strecke = modulverwaltung.dieses_modul.root.find("./Strecke")
    if strecke is not None:
        if args.modus == 'schreibe':
            for fahrstrasse_alt in strecke.findall("./Fahrstrasse"):
                strecke.remove(fahrstrasse_alt)
            for fahrstrasse_neu in sorted(fahrstrassen, key = lambda f: f.name):
                logging.info(fahrstrasse_neu.name)
                strecke.append(fahrstrasse_neu.to_xml())
            fp = tempfile.NamedTemporaryFile('wb', delete = False)
            with fp:
                fp.write(b"\xef\xbb\xbf")
                fp.write(u'<?xml version="1.0" encoding="UTF-8"?>\r\n'.encode("utf-8"))
                writeuglyxml(fp, modulverwaltung.dieses_modul.root)
            shutil.copyfile(fp.name, args.dateiname)
            os.remove(fp.name)

        elif args.modus == 'vergleiche':
            alt_vs_neu = defaultdict(dict)
            for fahrstrasse_alt in strecke.findall("./Fahrstrasse"):
                alt_vs_neu[fahrstrasse_alt.attrib["FahrstrName"]]["alt"] = fahrstrasse_alt
            for fahrstrasse_neu in fahrstrassen:
                alt_vs_neu[fahrstrasse_neu.name]["neu"] = fahrstrasse_neu

            for name, fahrstrassen in sorted(alt_vs_neu.items(), key = operator.itemgetter(0)):
                try:
                    fahrstr_alt = fahrstrassen["alt"]
                except KeyError:
                    print("{} existiert in Zusi nicht".format(name))
                    continue
                try:
                    fahrstr_neu = fahrstrassen["neu"]
                except KeyError:
                    print("{} existiert in Zusi, wurde aber nicht erzeugt".format(name))
                    continue

                laenge_alt = float(fahrstr_alt.get("Laenge", 0))
                if abs(laenge_alt - fahrstr_neu.laenge) > 1:
                    # print("{}: unterschiedliche Laenge: {:.2f} vs. {:.2f}".format(name, laenge_alt, fahrstr_neu.laenge))
                    pass

                fahrstr_typ = fahrstr_alt.get("FahrstrTyp", "")
                if fahrstr_neu.fahrstr_typ == FAHRSTR_TYP_RANGIER and fahrstr_typ != "TypRangier":
                    print("{}: unterschiedlicher Fahrstrassentyp: {} vs TypRangier".format(name, fahrstr_typ))
                elif fahrstr_neu.fahrstr_typ == FAHRSTR_TYP_ZUG and fahrstr_typ != "TypZug":
                    print("{}: unterschiedlicher Fahrstrassentyp: {} vs TypZug".format(name, fahrstr_typ))
                elif fahrstr_neu.fahrstr_typ == FAHRSTR_TYP_LZB and fahrstr_typ != "TypLZB":
                    print("{}: unterschiedlicher Fahrstrassentyp: {} vs TypLZB".format(name, fahrstr_typ))

                rgl_ggl_alt = int(fahrstr_alt.get("RglGgl", 0))
                if fahrstr_neu.rgl_ggl != rgl_ggl_alt:
                    print("{}: unterschiedliche RglGgl-Spezifikation: {} vs {}".format(name, rgl_ggl_alt, fahrstr_neu.rgl_ggl))

                streckenname_alt = fahrstr_alt.get("FahrstrStrecke", "")
                if fahrstr_neu.streckenname != streckenname_alt:
                    print("{}: unterschiedlicher Streckenname: {} vs {}".format(name, streckenname_alt, fahrstr_neu.streckenname))

                zufallswert_alt = float(fahrstr_alt.get("Zufallswert", 0))
                if fahrstr_neu.zufallswert != zufallswert_alt:
                    print("{}: unterschiedlicher Zufallswert: {} vs {}".format(name, zufallswert_alt, fahrstr_neu.zufallswert))

                start_alt = fahrstr_alt.find("./FahrstrStart")
                start_alt_refnr = int(start_alt.get("Ref", 0))
                start_alt_modul = start_alt.find("./Datei").get("Dateiname", "")
                if start_alt_refnr != fahrstr_neu.start.refnr or start_alt_modul.upper() != fahrstr_neu.start.element_richtung.element.modul.relpath.upper():
                    print("{}: unterschiedlicher Start: {}@{} vs. {}@{}".format(name, start_alt_refnr, start_alt_modul, fahrstr_neu.start.refnr, fahrstr_neu.start.element_richtung.element.modul.relpath))

                ziel_alt = fahrstr_alt.find("./FahrstrZiel")
                ziel_alt_refnr = int(ziel_alt.get("Ref", 0))
                ziel_alt_modul = ziel_alt.find("./Datei").get("Dateiname", "")
                if ziel_alt_refnr != fahrstr_neu.ziel.refnr or ziel_alt_modul.upper() != fahrstr_neu.ziel.element_richtung.element.modul.relpath.upper():
                    print("{}: unterschiedliches Ziel: {}@{} vs. {}@{}".format(name, ziel_alt_refnr, ziel_alt_modul, fahrstr_neu.ziel.refnr, fahrstr_neu.ziel.element_richtung.element.modul.relpath))

                # Register
                register_alt = set((int(register_alt.get("Ref", 0)), register_alt.find("./Datei").get("Dateiname", "").upper()) for register_alt in fahrstr_alt.iterfind("./FahrstrRegister"))
                register_neu = set((register_neu.refnr, register_neu.element_richtung.element.modul.relpath.upper()) for register_neu in fahrstr_neu.register)

                for refpunkt in register_alt - register_neu:
                    print("{}: Registerverknuepfung {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(refpunkt)))
                for refpunkt in register_neu - register_alt:
                    print("{}: Registerverknuepfung {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(refpunkt)))

                # Aufloesepunkte
                aufloesepunkte_alt = set((int(aufl.get("Ref", 0)), aufl.find("./Datei").get("Dateiname", "").upper()) for aufl in fahrstr_alt.iterfind("./FahrstrAufloesung"))
                aufloesepunkte_neu = set((aufl.refnr, aufl.element_richtung.element.modul.relpath.upper()) for aufl in fahrstr_neu.aufloesepunkte)

                for refpunkt in aufloesepunkte_alt - aufloesepunkte_neu:
                    print("{}: Aufloesepunkt {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(refpunkt)))
                for refpunkt in aufloesepunkte_neu - aufloesepunkte_alt:
                    print("{}: Aufloesepunkt {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(refpunkt)))

                # Signalhaltfallpunkte
                sighaltfallpunkte_alt = set((int(haltfall.get("Ref", 0)), haltfall.find("./Datei").get("Dateiname", "").upper()) for haltfall in fahrstr_alt.iterfind("./FahrstrSigHaltfall"))
                sighaltfallpunkte_neu = set((haltfall.refnr, haltfall.element_richtung.element.modul.relpath.upper()) for haltfall in fahrstr_neu.signalhaltfallpunkte)

                for refpunkt in sighaltfallpunkte_alt - sighaltfallpunkte_neu:
                    print("{}: Signalhaltfallpunkt {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(refpunkt)))
                for refpunkt in sighaltfallpunkte_neu - sighaltfallpunkte_alt:
                    print("{}: Signalhaltfallpunkt {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(refpunkt)))

                # Teilaufloesepunkte
                teilaufloesepunkte_alt = set((int(aufl.get("Ref", 0)), aufl.find("./Datei").get("Dateiname", "").upper()) for aufl in fahrstr_alt.iterfind("./FahrstrTeilaufloesung"))
                teilaufloesepunkte_neu = set((aufl.refnr, aufl.element_richtung.element.modul.relpath.upper()) for aufl in fahrstr_neu.teilaufloesepunkte)

                for refpunkt in teilaufloesepunkte_alt - teilaufloesepunkte_neu:
                    print("{}: Teilaufloesung {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(refpunkt)))
                for refpunkt in teilaufloesepunkte_neu - teilaufloesepunkte_alt:
                    print("{}: Teilaufloesung {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(refpunkt)))

                # Weichen
                weichenstellungen_alt_vs_neu = defaultdict(dict)
                for weiche_alt in fahrstr_alt.findall("./FahrstrWeiche"):
                    weichenstellungen_alt_vs_neu[(int(weiche_alt.get("Ref", 0)), weiche_alt.find("./Datei").get("Dateiname", "").upper())]["alt"] = int(weiche_alt.get("FahrstrWeichenlage", 0))
                for weiche_neu in fahrstr_neu.weichen:
                    weichenstellungen_alt_vs_neu[(weiche_neu.refpunkt.refnr, weiche_neu.refpunkt.element_richtung.element.modul.relpath.upper())]["neu"] = weiche_neu.weichenlage

                for weichen_refpunkt, weichenstellungen in sorted(weichenstellungen_alt_vs_neu.items(), key = operator.itemgetter(0)):
                    if "alt" not in weichenstellungen:
                        print("{}: Weichenstellung {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(weichen_refpunkt)))
                    elif "neu" not in weichenstellungen:
                        print("{}: Weichenstellung {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(weichen_refpunkt)))
                    elif weichenstellungen["alt"] != weichenstellungen["neu"]:
                        print("{}: Weiche {} hat unterschiedliche Stellungen: {} vs. {}".format(name, refpunkt_fmt(weichen_refpunkt), weichenstellungen["alt"], weichenstellungen["neu"]))

                # Hauptsignale
                hsig_alt_vs_neu = defaultdict(dict)
                for hsig_alt in fahrstr_alt.findall("./FahrstrSignal"):
                    hsig_alt_vs_neu[(int(hsig_alt.get("Ref", 0)), hsig_alt.find("./Datei").get("Dateiname", "").upper())]["alt"] = (int(hsig_alt.get("FahrstrSignalZeile", 0)), int(hsig_alt.get("FahrstrSignalErsatzsignal", 0)) == 1)
                for hsig_neu in fahrstr_neu.signale:
                    hsig_alt_vs_neu[(hsig_neu.refpunkt.refnr, hsig_neu.refpunkt.element_richtung.element.modul.relpath.upper())]["neu"] = (hsig_neu.zeile, hsig_neu.ist_ersatzsignal)

                for hsig_refpunkt, hsig in sorted(hsig_alt_vs_neu.items(), key = operator.itemgetter(0)):
                    if "alt" not in hsig:
                        print("{}: Hauptsignalverknuepfung {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(hsig_refpunkt)))
                    elif "neu" not in hsig:
                        print("{}: Hauptsignalverknuepfung {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(hsig_refpunkt)))
                    elif hsig["alt"] != hsig["neu"]:
                        print("{}: Hauptsignalverknuepfung {} hat unterschiedliche Zeile: {} vs. {}".format(name, refpunkt_fmt(hsig_refpunkt), hsig["alt"], hsig["neu"]))

                # Vorsignale
                vsig_alt_vs_neu = defaultdict(dict)
                for vsig_alt in fahrstr_alt.findall("./FahrstrVSignal"):
                    vsig_alt_vs_neu[(int(vsig_alt.get("Ref", 0)), vsig_alt.find("./Datei").get("Dateiname", "").upper())]["alt"] = int(vsig_alt.get("FahrstrSignalSpalte", 0))
                for vsig_neu in fahrstr_neu.vorsignale:
                    vsig_alt_vs_neu[(vsig_neu.refpunkt.refnr, vsig_neu.refpunkt.element_richtung.element.modul.relpath.upper())]["neu"] = vsig_neu.spalte

                for vsig_refpunkt, vsig in sorted(vsig_alt_vs_neu.items(), key = operator.itemgetter(0)):
                    if "alt" not in vsig:
                        print("{}: Vorsignalverknuepfung {} ist in Zusi nicht vorhanden".format(name, refpunkt_fmt(vsig_refpunkt)))
                    elif "neu" not in vsig:
                        print("{}: Vorsignalverknuepfung {} ist in Zusi vorhanden, wurde aber nicht erzeugt".format(name, refpunkt_fmt(vsig_refpunkt)))
                    elif vsig["alt"] != vsig["neu"]:
                        print("{}: Vorsignalverknuepfung {} hat unterschiedliche Spalte: {} vs. {}".format(name, refpunkt_fmt(vsig_refpunkt), vsig["alt"], vsig["neu"]))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fahrstrassengenerierung fuer ein Zusi-3-Modul')
    parser.add_argument('dateiname')
    parser.add_argument('--modus', choices=['schreibe', 'vergleiche'], default='schreibe', help=argparse.SUPPRESS)
    parser.add_argument('--profile', choices=['profile', 'line_profiler'], help=argparse.SUPPRESS)
    parser.add_argument('--debug', action='store_true', help="Debug-Ausgaben anzeigen")
    parser.add_argument('--nummerieren', action='store_true', help="Fahrstrassen mit gleichem Start+Ziel durchnummerieren (wie 3D-Editor 3.1.0.4)")
    args = parser.parse_args()

    logging.basicConfig(format='%(relativeCreated)d:%(levelname)s:%(message)s', level=(logging.DEBUG if args.debug else logging.INFO))

    if args.profile == 'profile':
        import profile, pstats
        p = profile.Profile()
        p.run('finde_fahrstrassen(args)')
        s = pstats.Stats(p)
        s.strip_dirs()
        s.sort_stats('cumtime')
        s.print_stats()
        s.print_callers()
    elif args.profile == 'line_profiler':
        import line_profiler
        p = line_profiler.LineProfiler(finde_fahrstrassen)
        # p.add_function(...)
        p.run('finde_fahrstrassen(args)')
        p.print_stats()
    else:
        finde_fahrstrassen(args)
