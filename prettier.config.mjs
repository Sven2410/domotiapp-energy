/**
 * De opmaakstijl die dit project al gebruikte, vastgelegd.
 *
 * **Dit is een rem en geen belofte.** De frontendbestanden zijn met de hand
 * opgemaakt en zijn nooit door Prettier gehaald — bij geen enkele printbreedte
 * komt hij op wat er staat. Deze config zorgt er alleen voor dat een kale run
 * niet óók nog enkele quotes in dubbele verandert; wie `--write` over de hele
 * map draait, herformatteert nog steeds honderden regels die niemand heeft
 * aangeraakt.
 *
 * Dat is precies één keer gebeurd, in 0.23.0, en het kostte een ronde om de
 * ruis er weer uit te halen: vijftien regels die anders afbraken maakten de
 * diff onleesbaar voor de review.
 *
 * **Dus: draai Prettier op de bestanden die je zelf hebt bewerkt, niet op de
 * map.** Een JS-configbestand in plaats van JSON, omdat deze uitleg naast de
 * waarden hoort te staan en JSON geen commentaar kent.
 */
export default {
  singleQuote: true,
  printWidth: 88,
};
