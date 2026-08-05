/**
 * The Energiebronnen tab (SPEC.md §8).
 *
 * Placeholder until phase 8.
 * The id is English and fixed like every other identifier in this project; only
 * the label the customer reads is Dutch.
 */

import { placeholderTab } from '../core/dom.js';

export const sourcesTab = placeholderTab({
  id: 'sources',
  label: 'Energiebronnen',
  icon: 'mdi:transmission-tower',
  adminOnly: true,
  description:
    'Hier koppel je je slimme meter, omvormer, prijsbron of thuisbatterij aan DomotiApp Energy.',
});
