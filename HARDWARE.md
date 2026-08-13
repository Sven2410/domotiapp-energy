# HARDWARE.md — wat we van merken en integraties hebben gezien

Dit bestand verzamelt waarnemingen aan **andermans apparatuur**: omvormers,
laadpalen, meters en de Home Assistant-integraties die ze ontsluiten. Het groeit
met elke klant die anders is dan de vorige.

## Waarom dit niet in SPEC.md staat

1. **Andere soort uitspraak.** SPEC legt vast wat het product moet doen voor
   iedere klant — beslissingen van ons. Dit zijn waarnemingen aan apparatuur die
   wij niet kunnen veranderen en niet kunnen afdwingen.
2. **Ander ritme.** SPEC verandert wanneer wij iets besluiten; dit wanneer we
   iets zien. Elke nieuwe woning kan hier een regel bijzetten, en per merk groeit
   dat: in SPEC zou het de functionele tekst wegdrukken.
3. **Andere lezer.** Een tweede installateur die een vreemde omvormer treft
   zoekt *"wat weten we van dit merk"*, niet paragraaf 47.

Het staat bewust **niet** in `custom_components/`: er wordt niets van
meegeleverd aan de klant.

## Twee regels

**1. Elke waarneming noemt de installatie waar zij vandaan komt.** Datum, welke
woning, welke integratie en versie voor zover bekend, en hoe het gemeten is. Ziet
een tweede woning hetzelfde, dan wordt dat een tweede regel of een telling — geen
generalisatie. Eén woning is een steekproef van één, ook als het antwoord snel
kwam.

**2. Geen code vertakt ooit op merk.** Geen `if merk == …` in
`custom_components/`, geen merknaam in een constante, geen drempel die voor één
fabrikant is gekozen. Merkkennis **verklaart** waarom een grens gekozen is; zij
**stuurt** niet. Wat een apparaat van een soort kan, hoort in de motor te passen
voor elk apparaat van die soort; wat één merk doet, hoort hier.

Dat is dezelfde grens die SPEC §38 trok toen machinerie werd opgeruimd voor een
geval dat nog niemand had gezien: een waarneming rechtvaardigt een aantekening,
niet meteen een mechanisme.

## Vorm per merk

Drie kopjes, en ze mogen niet door elkaar lopen:

- **Waargenomen** — wat er gemeten is, met datum en bron.
- **Afgeleid** — wat wij eruit concluderen, en waar dat gebruikt is.
- **Niet gemeten** — wat we van dit merk juist niet weten.

---

# SolarEdge — `solaredge_modbus_multi`

Woning Sven, driefase 25 A, `sensor.solaredge_i1_ac_power`, gemeten via de
recorder-historie op 2026-08-13.

## Waargenomen

**Dageraadpieken op een vast raster.** Kort na de eerste opwek van de dag meldt
de omvormer één meting lang een vermogen dat een veelvoud van de werkelijke
opwek is, en valt daarna terug. Zeven keer op zes dagen, en elke keer op
**632–634 s of 1266–1267 s** na de eerste opwek — één of twee veelvouden van
ongeveer 633 s. Het interval tussen de twee pieken van 2026-08-13 is 634 s, en
dat is zonder "eerste opwek" gerekend: de periodiciteit zit in de meting.

| dag | eerste opwek | piek | s erna | W | basislijn |
|---|---|---|---|---|---|
| 08-05 | 06:22:44 | 06:43:50 | 1266 | 200 | 55 |
| 08-06 | 06:20:21 | 06:30:53 | 632 | 88 | 43 |
| 08-09 | 06:24:59 | 06:35:33 | 634 | 116 | 48 |
| 08-10 | 06:25:41 | 06:46:47 | 1266 | 209 | 75 |
| 08-12 | 06:28:31 | 06:49:37 | 1266 | 398 | 69 |
| 08-13 | 06:31:33 | 06:42:06 | 633 | 499 | 46 |
| 08-13 | 06:31:33 | 06:52:40 | 1267 | 180 | 62 |

**Het houdt daarna op.** Na de tweede piek is de grootste afwijking van de eigen
omgeving in de rest van de ochtend +16 W. Alles later op de dag dat op een piek
lijkt, is bewolking: verspreid over de dag, met basislijnen van 38 tot 3712 W.

**De modbuspoort gaat 's nachts niet dicht.** Bij deze firmware blijft de sensor
0 W rapporteren; hij wordt niet `unavailable` en veroudert niet. De nacht van
2026-08-12 op 08-13 leverde één onderbreking van 30 seconden op, om 23:01.

**Een reload van de config-entry zet de entiteiten kortstondig op
`unavailable`.** Direct waargenomen op 2026-08-13 om 11:05:54: twee seconden later
schreef ons logboek terecht één `source_unavailable`, om 11:06:10 weer dicht.

Dit is **het enige merk waarvan we een kortstondige blanco hebben gezien.** De
prijsbron leek hetzelfde te doen en doet het niet; zie Frank Energie hieronder.

## Afgeleid

- **Een vermogensbron kan één meting lang een fysiek onmogelijke waarde melden.**
  Dat is geen eigenschap van dit merk: een templatesensor of een meter kan het
  net zo goed. Er staat daarom **geen** filter in de motor — zie regel 2.
- **Het bereikt de motor zelden.** De piek duurt ongeveer één seconde en de
  coordinator herberekent gedebounced per 15 s; van de zeven pieken landde er één
  in een berekening (2026-08-12 06:49:37, thuisverbruik één meting lang 969 W in
  plaats van ~520 W).
- **De kantelpunten staan in SPEC §63.7** en volgen uit de formules: score-
  inflatie vraagt teruglevering op het moment van de piek, vals zonneadvies
  vraagt `P_piek ≥ verbruik + min_solar_surplus_w`. Bij deze woning wordt geen van
  beide gehaald.
- **Een blanco tijdens een reload is te onderscheiden van een echte uitval,
  zonder tijdgrens.** Home Assistant weet zelf of de integratie op dat moment
  tussen twee levens in zit: `ConfigEntry.state` draagt onder meer
  `SETUP_IN_PROGRESS`, `UNLOAD_IN_PROGRESS` en `NOT_LOADED`, en de
  entiteitenregistratie geeft via `config_entry_id` welke entry bij een entiteit
  hoort (geverifieerd op HA 2026.8.1). Dat is een feit op dat moment, geen
  wachttijd.

  **Dit is bewust niet gebouwd.** Eén merk, één mechanisme, en de enige keer dat
  het vuurde was de melding waar: de bron *was* onleesbaar, en juist die regel
  bracht Svens 07:00-automatisering aan het licht. Zou dit gebouwd worden, dan
  mag `SETUP_RETRY` er nooit onder vallen — een integratie die blijft mislukken
  op te starten is wél een storing.

## De schade per configuratie, uit de formules

Met **P** = piekwaarde, **b** = werkelijke opwek op dat moment, **V** = huisverbruik,
**S** = `min_solar_surplus_w` (standaard 500 W).

| woning | wat er misgaat | wanneer het kantelt |
|---|---|---|
| **mét netmeter** — advies | niets, ooit. Het overschot komt uit `max(-netvermogen, 0)` en leest de zonnesensor niet | nooit |
| **mét netmeter** — thuisverbruik | één meting lang **P − b** te hoog (`net + opwek − batterij`) | altijd, ongeacht V |
| **mét netmeter** — zelfbenutting en score | de teruglevering komt van de meter, dus bij import is de uitkomst 100% wat de piek ook doet. Levert de woning terug, dan wordt `V/b` opgetrokken richting 100% | **V < b** |
| **zonder netmeter** — vals zonneadvies | overschot = P − V, dus de piek wordt overschot | **P ≥ V + S** |
| **laag basisverbruik** | versterkt beide: maakt `V < b` waarschijnlijk en verlaagt de lat `P ≥ V + S` | — |
| **hoog basisverbruik** | beschermt tegen beide | — |

Op de gemeten woning (V ≈ 520 W, dageraadbasislijn b = 43–75 W, grootste P = 499 W, mét
netmeter) wordt geen van beide grenzen gehaald. Dat is **die woning**, niet het product.

**En er zit een tweede rem op, gemeten:** de piek duurt ongeveer één seconde en de
coordinator herberekent gedebounced per 15 s, dus van zeven pieken landde er **één** in een
berekening. Ook waar de rekenkunde kantelt, is de verwachte frequentie laag.

## Waarom hier geen filter staat

**Het onderscheidende kenmerk van het artefact — omhoog en meteen terug naar dezelfde
basislijn — is precies het kenmerk van een zonneflits door een wolkengat.** In dezelfde elf
dagen telde `scripts/solar_spikes.py` op dit dak **7** dageraadpieken en **40** van die
weersovergangen. Een filter dat ruim genoeg staat om de kleinste dageraadpiek (88 W) te
vangen, gooit dus ook echte instraling weg — en dat zijn juist de momenten waarop een
batterij of laadpaal terecht reageert.

Een filter zou hier meer kapotmaken dan het repareert, en dat volgt uit de meting en niet
uit een voorkeur.

## Niet gemeten

Andere firmware, een andere omvormergrootte, een ander aantal strings, en het
gedrag bij zonsondergang: er is één waarneming (2026-08-04 20:32, 191 W op een
basislijn van 38 W) die mogelijk hetzelfde verschijnsel bij het uitschakelen is,
maar zij ligt niet op het 633 s-raster en staat alleen.

---

# Frank Energie — `frank_energie`

Woning Sven, `sensor.current_electricity_price_all_in`
(`unique_id: frank_energie.elec_markup`), gemeten op 2026-08-13.

## Waargenomen

**De entiteit gaat nooit blanco.** Tien dagen recorderhistorie, 257 wijzigingen,
**nul** `unknown` of `unavailable`. Zij verandert precies op het hele uur, elke
dag, zonder uitzondering — 25 wijzigingen per dag, allemaal op minuut 0.

**En zij herhaalt zich niet tussendoor.** Negen metingen over vijf minuten:
`last_reported` bleef staan op `11:00:00Z` terwijl de waarde 0,1346 bleef. Frank
schrijft één keer per uur en verder niets.

**Wat het logboek 103 keer meldde, was daarom onze eigen veroudering.** Van 7
augustus 21:29 tot 10 augustus 00:34 stond er onafgebroken een klok in het
logboek — negentien uur lang elk uur op `:29:42`, daarna op `:15` en `:45`. Dat
ritme is het veiligheidsinterval dat een bron aantreft die legitiem een uur
zwijgt, niet een bron die uitvalt.

## Afgeleid

- **Een prijsbron zwijgt een uur aan één stuk, en dat is geen storing.** Onder
  het oude venster van 15 minuten was deze bron 45 van elke 60 minuten
  onleesbaar, permanent. Sinds 0.12.0 (SPEC §47) geldt 90 minuten voor
  prijsbronnen en is zij altijd leesbaar.
- **De marge is 30 minuten.** 60 minuten stilte tegen een venster van 90. Een
  prijsintegratie die per twee uur schrijft — bijvoorbeeld omdat zij de prijzen
  van morgen in blokken publiceert — loopt hier opnieuw tegenaan, op precies
  dezelfde manier. Dat is de aanname die nog staat.
- Niets hiervan zit merkgebonden in de motor: `SOURCE_STALE_MINUTES` kiest per
  **brontype**, niet per merk, en een guard-test dwingt af dat een nieuw type
  zijn eigen keuze maakt.

## Niet gemeten

Wanneer Frank vóór 10 augustus precies schreef. Uit de logboekregels valt af te
leiden dat het toen op ongeveer `:14` was en later op `:00`/`:30`, maar de
recorder bewaart alleen wijzigingen en geen herhalingen, dus dat is een gevolg-
trekking en geen meting. Ook niet gemeten: of de cadans verandert rond het
moment dat de prijzen voor de volgende dag bekend worden.

---

# Easee — laadpaal

Woning 3 (2026-08-10) en de eigen paal van Sven (bevestigd 2026-08-11).

## Waargenomen

- **De paal moduleert.** Een paal met een maximum van 3680 W laadt op een
  overschot van 2100 W gewoon door, op ongeveer 9 A.
- **Onder ongeveer 6 A laadt een auto niet.** Dat minimum is een eigenschap van
  de **auto**, niet van de paal — twee auto's aan dezelfde paal kunnen het
  verschillend hebben.
- De meting van Svens paal is **driefasig**, niet eenfasig; dat is waar het
  minimumvermogen in watt uit volgt.

## Afgeleid

Modulatie is een eigenschap die elk apparaat van deze soort kan hebben, geen
merkkenmerk. Zij zit daarom in de motor als `can_modulate` + `min_power_w`
(SPEC §56), additief: een niet-modulerend apparaat wordt nog steeds op zijn
`nominal_power_w` beoordeeld, en `min_power_w` heeft geen standaardwaarde.

## Niet gemeten

Andere laadpaalmerken, en of een tweede auto aan dezelfde paal in de praktijk
een ander minimum vraagt dan de eerste.
