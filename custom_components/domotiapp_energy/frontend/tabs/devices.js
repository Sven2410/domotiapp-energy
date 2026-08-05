/**
 * The Apparaten tab (SPEC.md §8).
 *
 * Placeholder until phase 8.
 * The id is English and fixed like every other identifier in this project; only
 * the label the customer reads is Dutch.
 */

import { placeholderTab } from '../core/dom.js';

export const devicesTab = placeholderTab({
  id: 'devices',
  label: 'Apparaten',
  icon: 'mdi:washing-machine',
  adminOnly: true,
  description:
    'Hier voeg je apparaten toe waarover DomotiApp Energy kan adviseren, met hun vermogen, verbruik per cyclus en tijdvenster.',
});
