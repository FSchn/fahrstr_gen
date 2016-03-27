#!/usr/bin/env python3

from fahrstr_gen import modulverwaltung, streckengraph, strecke
from fahrstr_gen.konstanten import *
from fahrstr_gen.strecke import writeuglyxml

import xml.etree.ElementTree as ET
import argparse

import logging
logging.basicConfig(level = logging.INFO)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fahrstrassengenerierung fuer ein Zusi-3-Modul')
    parser.add_argument('dateiname')
    args = parser.parse_args()

    dieses_modul_relpath = modulverwaltung.get_zusi_relpath(args.dateiname)
    modulverwaltung.dieses_modul = modulverwaltung.Modul(dieses_modul_relpath.replace('/', '\\'), ET.parse(args.dateiname).getroot())
    modulverwaltung.module[modulverwaltung.normalize_zusi_relpath(dieses_modul_relpath)] = modulverwaltung.dieses_modul

    fahrstrassen = []
    for fahrstr_typ in [FAHRSTR_TYP_ZUG, FAHRSTR_TYP_LZB]:
        graph = streckengraph.Streckengraph(fahrstr_typ)

        for nr, str_element in sorted(modulverwaltung.dieses_modul.streckenelemente.items(), key = lambda t: t[0]):
            if str_element in modulverwaltung.dieses_modul.referenzpunkte:
                for richtung in [NORM, GEGEN]:
                    if any(
                            (fahrstr_typ == FAHRSTR_TYP_ZUG and r.reftyp == REFTYP_AUFGLEISPUNKT)
                            or (r.reftyp == REFTYP_SIGNAL and strecke.ist_hsig_fuer_fahrstr_typ(r.signal(), fahrstr_typ))
                            for r in modulverwaltung.dieses_modul.referenzpunkte[str_element] if r.richtung == richtung
                        ):

                        fahrstrassen.extend(graph.get_knoten(modulverwaltung.dieses_modul, str_element).get_fahrstrassen(richtung))

    strecke = modulverwaltung.dieses_modul.root.find("./Strecke")
    if strecke is not None:
        for fahrstrasse_alt in strecke.findall("./Fahrstrasse"):
            strecke.remove(fahrstrasse_alt)
        for fahrstrasse_neu in sorted(fahrstrassen, key = lambda f: f.name):
            logging.info(fahrstrasse_neu.name)
            strecke.append(fahrstrasse_neu.to_xml())
        with open(args.dateiname, 'wb') as fp:
            fp.write(b"\xef\xbb\xbf")
            fp.write(u'<?xml version="1.0" encoding="UTF-8"?>\r\n'.encode("utf-8"))
            writeuglyxml(fp, modulverwaltung.dieses_modul.root)
