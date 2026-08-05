/**
 * The Voorkeuren tab (SPEC.md §8).
 *
 * Placeholder until phase 8.
 * The id is English and fixed like every other identifier in this project; only
 * the label the customer reads is Dutch.
 */

import { placeholderTab } from '../core/dom.js';

export const preferencesTab = placeholderTab({
  id: 'preferences',
  label: 'Voorkeuren',
  icon: 'mdi:tune',
  adminOnly: true,
  description:
    'Hier stel je de stille uren, de adviesvoorkeuren en het maximale aantal adviezen in.',
});
