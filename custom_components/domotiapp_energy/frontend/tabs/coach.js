/**
 * The Energiecoach tab (SPEC.md §8).
 *
 * Placeholder until phase 8.
 * The id is English and fixed like every other identifier in this project; only
 * the label the customer reads is Dutch.
 */

import { placeholderTab } from '../core/dom.js';

export const coachTab = placeholderTab({
  id: 'coach',
  label: 'Energiecoach',
  icon: 'mdi:lightbulb-on-outline',
  adminOnly: false,
  description:
    'Hier zie je alle adviezen met hun onderbouwing, de ontbrekende gegevens en de opbouw van je energiescore.',
});
