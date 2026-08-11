/**
 * Wat het paneel over een apparaat weet zonder het aan de motor te vragen.
 *
 * Twee tabbladen stellen dezelfde vragen over een apparaat — Apparaten om het
 * formulier te bouwen, het Overzicht om te bepalen of er een handeling bij
 * hoort — en die vragen mogen niet op twee plekken een eigen antwoord krijgen
 * (SPEC.md §60). Vandaar deze module: één antwoord per vraag, en de tabbladen
 * lezen het.
 *
 * De zinnen over de gereed-vlag horen hier om precies dezelfde reden. Zij
 * stonden in 0.23.0 woord voor woord in twee bestanden, en dat is de vorm die
 * uiteen loopt zodra iemand er één herschrijft.
 */

import { formatMoment } from './dom.js';

/**
 * Types die de coach nooit kan aanspreken (`const.NEVER_ADVISED_DEVICE_TYPES`).
 *
 * Een thuisbatterij is flexibel — energie door de tijd verplaatsen is wat zij
 * doet — dus de vlag zegt ja en het apparaat werd adviseerbaar, waarna de
 * checklist om een energie per cyclus vroeg. Die heeft zij niet: niemand start
 * een batterij, zij volgt het overschot vanzelf (SPEC.md §38.2).
 */
export const NEVER_ADVISED_TYPES = ['home_battery'];

/** Types die niet verplaatsbaar zijn tenzij de installateur iets anders zegt. */
export const INFLEXIBLE_BY_DEFAULT = new Set(['generic_monitor', 'heat_pump']);

/**
 * Types die iemand met de hand vult, dus wacht de coach tot hij het hoort
 * (SPEC.md §32.5).
 *
 * Een laadpaal staat er bewust niet bij: die ziet via zijn statusentiteit zelf
 * of er een auto hangt, en een vlag die iemand moet omzetten terwijl het
 * systeem het antwoord kan zien is precies het invulwerk dat §32 wegneemt.
 */
export const NEEDS_READY_FLAG_BY_DEFAULT = new Set([
  'dishwasher',
  'washing_machine',
  'dryer',
]);

/** Of dit type standaard verplaatsbaar is (SPEC.md §8). */
export function flexibleByDefault(deviceType) {
  return !INFLEXIBLE_BY_DEFAULT.has(deviceType);
}

/** Of dit type standaard wacht tot iemand zegt dat er werk in zit (§32.5). */
export function needsReadyFlagByDefault(deviceType) {
  return NEEDS_READY_FLAG_BY_DEFAULT.has(deviceType);
}

/**
 * Of de coach ooit iets over dit apparaat kan zeggen.
 *
 * De kopie van `engine/completeness.py:is_advisable` in het paneel. Beide assen
 * tellen: het type bepaalt de standaardflexibiliteit, en het bedieningsniveau
 * is de eigen uitknop van de bewoner.
 */
export function isAdvisable(device) {
  if (NEVER_ADVISED_TYPES.includes(device.device_type)) {
    return false;
  }
  const flexible =
    device.is_flexible === undefined || device.is_flexible === null
      ? flexibleByDefault(device.device_type)
      : device.is_flexible;
  return Boolean(flexible) && device.control_mode !== 'monitor_only';
}

/**
 * Of de bewoner van dit apparaat iets gevraagd wordt op het Overzicht.
 *
 * **Twee vragen, en de tweede wordt makkelijk vergeten** (SPEC.md §60.2). Het
 * apparaat moet een gereed-vlag nodig hebben, én de coach moet er iets over
 * kunnen zeggen — want de vlag voedt alleen het urgentie-advies. Een vaatwasser
 * die de bewoner op *Alleen meekijken* heeft gezet, krijgt geen advies, dus een
 * knop erbij zou vragen om iets dat niemand leest.
 *
 * Dat is dezelfde toepasselijkheidsregel als bij het tijdvenster en het
 * apparaatprofiel (SPEC.md §16): een handeling hangt aan waar haar uitkomst
 * voor gebruikt wordt, niet aan het bestaan van de rij.
 */
export function asksSomethingOfTheResident(device) {
  return (
    Boolean(device.enabled) && Boolean(device.needs_ready_flag) && isAdvisable(device)
  );
}

/**
 * Zeg hoelang "hij is vol" waar blijft, in de woorden die iemand zou gebruiken.
 *
 * **Twee hele zinnen, en welke je krijgt is geen detail** (SPEC.md §32.6). Met
 * een status- of resttijdentiteit gaat de vlag vanzelf uit zodra het programma
 * eindigt en is de vervaltermijn een vangnet. Zonder zo'n koppeling is
 * vervallen de *enige* manier waarop hij ooit uitgaat, en dat hoort de bewoner
 * te weten op het moment dat hij drukt — niet wanneer hij zich afvraagt waarom
 * er niets gebeurde.
 *
 * Het moment staat er in beide gevallen bij, want wie 's avonds om tien uur
 * zijn vaatwasser vult, moet weten dat het morgenochtend nog geldt.
 */
export function describeReadyFlag(flag) {
  if (!flag) {
    return '';
  }
  const until = formatMoment(flag.expires_at);
  if (flag.auto_clears) {
    return `Staat vol. Dit vervalt ${until}, of eerder zodra hij klaar is.`;
  }
  return (
    `Staat vol. We kunnen niet zien wanneer hij klaar is, dus dit blijft ` +
    `staan tot ${until}. Zet het eerder uit als er niets meer in zit.`
  );
}
