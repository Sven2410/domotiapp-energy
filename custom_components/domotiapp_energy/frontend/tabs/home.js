/**
 * The Woning tab (SPEC.md §8).
 *
 * Placeholder until phase 7b, which builds this form on the ha-form wrapper in core/forms.js.
 * The id is English and fixed like every other identifier in this project; only
 * the label the customer reads is Dutch.
 */

import { placeholderTab } from '../core/dom.js';

export const homeTab = placeholderTab({
  id: 'home',
  label: 'Woning',
  icon: 'mdi:home-outline',
  adminOnly: true,
  description:
    'Hier stel je de fasen, de hoofdzekering, het maximale netvermogen, het contracttype en de prijsgrenzen van deze woning in.',
});
