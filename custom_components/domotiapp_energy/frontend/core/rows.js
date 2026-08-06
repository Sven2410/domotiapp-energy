/**
 * A list that is updated by id, never re-rendered (SPEC.md §9).
 *
 * "Voor dynamische lijsten gericht items toevoegen/wijzigen/verwijderen op basis
 * van `id`" is the rule, and this is the one place that implements it. Rebuilding
 * the list on every update would be shorter and would throw away focus, scroll
 * position and any button the installer was halfway through pressing — on the
 * exact screen where they are working through a row at a time.
 *
 * The caller supplies a factory that builds one row and returns its `update`
 * function; `sync()` then does the bookkeeping: reuse what is still there,
 * create what is new, remove what is gone, and put them in the given order.
 */

import { el, setVisible } from './dom.js';

/**
 * Create a keyed list.
 *
 * @param createRow builds one row, returning `{ element, update(item) }`
 * @param emptyText what to show when there is nothing yet — never a blank area,
 *   which reads as a defect rather than as an empty list (SPEC.md §8)
 */
export function createRowList({ createRow, emptyText }) {
  const rows = new Map();
  const list = el('div', { class: 'row-list' });
  const empty = el('p', { class: 'empty-text', text: emptyText });
  const element = el('div', {}, [list, empty]);

  return {
    element,

    /** Bring the list in line with these items, touching as little as possible. */
    sync(items) {
      const seen = new Set();

      for (const item of items) {
        seen.add(item.id);
        let row = rows.get(item.id);
        if (!row) {
          row = createRow(item);
          rows.set(item.id, row);
        }
        row.update(item);
      }

      for (const [id, row] of rows) {
        if (!seen.has(id)) {
          row.element.remove();
          rows.delete(id);
        }
      }

      // Re-appending an element that is already in the right place is a no-op
      // in the DOM, so this both orders and inserts without a rebuild.
      for (const item of items) {
        list.appendChild(rows.get(item.id).element);
      }

      setVisible(empty, items.length === 0);
      setVisible(list, items.length > 0);
    },
  };
}
