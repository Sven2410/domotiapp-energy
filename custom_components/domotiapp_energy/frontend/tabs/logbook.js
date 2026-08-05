/**
 * The Logboek tab (SPEC.md §8).
 *
 * Placeholder until phase 8.
 * The id is English and fixed like every other identifier in this project; only
 * the label the customer reads is Dutch.
 */

import { placeholderTab } from '../core/dom.js';

export const logbookTab = placeholderTab({
  id: 'logbook',
  label: 'Logboek',
  icon: 'mdi:format-list-bulleted',
  adminOnly: false,
  description:
    'Hier zie je wat DomotiApp Energy heeft gesignaleerd: configuratiewijzigingen, onbeschikbare bronnen en piekmomenten.',
});
