/**
 * The Installatie tab (SPEC.md §33.6).
 *
 * Woning and Energiebronnen used to be two tabs. They are two sections of one
 * now, because they answer the same question — what is this house, and what do
 * we measure it with — and because seven tabs is too many for a resident who
 * should have to search as little as possible.
 *
 * **This is a mount, not a merge.** The two forms keep their own modules, their
 * own drafts and their own save cycles; nothing about them changed except where
 * they appear. Folding nine hundred lines of home form and nine hundred of
 * source form into one file would have been a rewrite in service of a tab bar.
 *
 * The whole tab is installer territory (SPEC.md §33.4), so for a resident every
 * field in both sections is disabled and both say who manages them. Not hidden:
 * seeing that the main fuse is wrong is the entire point of showing it to him.
 */

import { el } from '../core/dom.js';
import { homeTab } from './home.js';
import { sourcesTab } from './sources.js';

/** The sections, in the order they are stacked. */
const SECTIONS = [homeTab, sourcesTab];

/**
 * Ask each section in turn whether the panel may leave.
 *
 * A section with unsaved changes answers false and asks the question itself
 * (SPEC.md §22); the callback is how it says "go ahead" afterwards. Recursive
 * rather than a loop because that answer arrives later: when the first section
 * refuses, the rest still has to be asked once the user has resolved it, and
 * only when every section agrees may the panel actually move.
 */
function canLeaveAll(sections, proceed) {
  const [first, ...rest] = sections;
  if (!first) {
    return true;
  }
  const askTheRest = () => {
    if (canLeaveAll(rest, proceed)) {
      proceed();
    }
  };
  if (first.canLeave && !first.canLeave(askTheRest)) {
    return false;
  }
  return canLeaveAll(rest, proceed);
}

export const installationTab = {
  id: 'installation',
  label: 'Installatie',
  icon: 'mdi:home-lightning-bolt-outline',

  create(context) {
    const element = el('div', { class: 'tab-content' });
    const sections = SECTIONS.map((definition) => {
      const instance = definition.create(context);
      // Each section keeps an id of its own. It is not a tabpanel — the tab
      // around it is — but it is the handle anything looking for one half of
      // this tab needs, tests included.
      instance.element.id = `section-${definition.id}`;
      return instance;
    });

    for (const section of sections) {
      element.appendChild(section.element);
    }

    return {
      element,
      update(state) {
        for (const section of sections) {
          section.update(state);
        }
      },
      canLeave(proceed) {
        return canLeaveAll(sections, proceed);
      },
    };
  },
};
