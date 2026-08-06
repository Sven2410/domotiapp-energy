/**
 * Tests for the Woning tab (SPEC.md §8, §9 and §22).
 *
 * The save cycle is the part worth pinning. Every claim SPEC.md §22 makes about
 * it is a promise to an installer standing in someone's meter cupboard: the
 * fields lock while a save is in flight, nothing says "saved" before the
 * backend agrees, a refusal is shown in Dutch, a stale revision reloads instead
 * of overwriting, and unsaved changes are not silently thrown away by clicking
 * another tab.
 *
 * As everywhere in this panel, visibility is asserted through the `is-hidden`
 * class rather than through jsdom's computed styles.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  clickTab,
  fakeHass,
  isVisible,
  mountPanel,
  sampleConfig,
  settle,
  tabPanels,
} from './harness.mjs';

/** The Woning tab, built by opening it. */
async function openHomeTab(hass = fakeHass()) {
  const panel = await mountPanel(hass);
  clickTab(panel, 'Woning');
  await settle();
  const tab = tabPanels(panel).find((node) => node.id === 'panel-home');
  return { panel, tab };
}

/** Every ha-form in the tab, in the order the cards appear. */
function forms(tab) {
  return [...tab.querySelectorAll('ha-form')];
}

/**
 * The three forms the installer can actually edit.
 *
 * The fourth is the control level, which is disabled for the life of the panel
 * because 0.1.0 controls nothing — so it must be left out of any assertion
 * about what a save does and undoes.
 */
function editableForms(tab) {
  return forms(tab).slice(0, 3);
}

/** Simulate the installer changing one field. */
function change(tab, values, formIndex = 0) {
  const form = forms(tab)[formIndex];
  form.data = { ...form.data, ...values };
  form.dispatchEvent(
    new tab.ownerDocument.defaultView.CustomEvent('value-changed', {
      detail: { value: form.data },
    }),
  );
}

function findButton(tab, label) {
  const found = [...tab.querySelectorAll('button')].find((node) =>
    node.textContent.includes(label),
  );
  if (!found) {
    throw new Error(`No button labelled ${label}`);
  }
  return found;
}

function noticeTexts(tab) {
  return [...tab.querySelectorAll('.notice')]
    .filter(isVisible)
    .map((node) => node.querySelector('.notice-text').textContent);
}

describe('the form itself', () => {
  it('uses ha-form with a schema, never hand-built inputs', async () => {
    const { tab } = await openHomeTab();

    // Four forms: three editable cards plus the fixed control level.
    assert.equal(forms(tab).length, 4);
    for (const form of forms(tab)) {
      assert.ok(Array.isArray(form.schema) && form.schema.length > 0);
    }
    // No loose primary controls (SPEC.md §9).
    assert.equal(tab.querySelectorAll('ha-textfield, ha-select, ha-switch').length, 0);
  });

  it('carries the two net metering fields with the per-kWh warning', async () => {
    const { tab } = await openHomeTab();
    const contract = forms(tab)[1];
    const names = contract.schema.map((field) => field.name);

    assert.ok(names.includes('feed_in_cost_eur_kwh'));
    assert.ok(names.includes('net_metering_until'));

    const cost = contract.schema.find(
      (field) => field.name === 'feed_in_cost_eur_kwh',
    );
    // Entering a monthly band here would be wrong by two orders of magnitude.
    assert.match(cost.helper, /per teruggeleverde kWh/);
    assert.match(cost.helper, /géén vast maandbedrag/);
  });

  it('asks for the price composition per kWh, not per month', async () => {
    const { tab } = await openHomeTab();
    // The composition belongs to a dynamic contract; a fixed one is not asked.
    change(tab, { contract_type: 'dynamic' }, 1);
    const contract = forms(tab)[1];
    const field = (name) => contract.schema.find((entry) => entry.name === name);

    // Without these three a market price cannot be completed to an all-in one,
    // and the engine refuses the price source (SPEC.md §16).
    assert.ok(field('energy_tax_eur_kwh'));
    assert.ok(field('vat_percent'));

    const markup = field('supplier_markup_eur_kwh');
    // The same trap as the feed-in cost: a monthly amount here is wrong by
    // orders of magnitude.
    assert.match(markup.helper, /per kWh/);
    assert.match(markup.helper, /géén vast maandbedrag/);
  });

  it('says that the price thresholds are all-in amounts', async () => {
    const { tab } = await openHomeTab();
    change(tab, { contract_type: 'dynamic' }, 1);
    const contract = forms(tab)[1];

    for (const name of [
      'low_price_threshold_eur_kwh',
      'high_price_threshold_eur_kwh',
    ]) {
      const field = contract.schema.find((entry) => entry.name === name);
      // Entering what a market-price sensor shows would set the threshold about
      // three times too low, and nothing downstream could notice.
      assert.match(field.label, /all-in/);
      assert.match(field.helper, /niet.*met de kale marktprijs/);
    }
  });

  it('describes the feed-in payment as a fixed amount that is never converted', async () => {
    const { tab } = await openHomeTab();
    const contract = forms(tab)[1];
    const field = contract.schema.find(
      (entry) => entry.name === 'feed_in_price_eur_kwh',
    );

    assert.match(field.helper, /per teruggeleverde kWh/);
    assert.match(field.helper, /niet omgerekend/);
  });

  it('explains the all-in formula once, next to the price fields', async () => {
    const { tab } = await openHomeTab();

    const explanation = noticeTexts(tab).find((text) => text.includes('all-in'));
    assert.match(explanation, /marktprijs \+ opslag \+ energiebelasting/);
    assert.match(explanation, /btw/);
  });

  it('sends the new price fields along with the rest of the profile', async () => {
    const sent = [];
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      sent.push(message);
      if (message.type === 'domotiapp_energy/home/update') {
        return { revision: 8, item: { ...message.home } };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    // The composition belongs to a dynamic contract, so it has to be in force
    // before these fields exist. Editing them on a fixed contract is something
    // `ha-form` cannot do either: it does not render them, so it can never emit
    // them — and a test that did it anyway was leaning on the merge bug this
    // card used to have.
    change(tab, { contract_type: 'dynamic' }, 1);
    change(tab, { energy_tax_eur_kwh: 0.1088, supplier_markup_eur_kwh: 0.02 }, 1);
    findButton(tab, 'Opslaan').click();
    await settle();

    const update = sent.find(
      (message) => message.type === 'domotiapp_energy/home/update',
    );
    assert.equal(update.home.energy_tax_eur_kwh, 0.1088);
    assert.equal(update.home.supplier_markup_eur_kwh, 0.02);
    // Untouched, so it travels as whatever the backend already had.
    assert.ok('vat_percent' in update.home);
  });

  it('puts a backend validation message on the field it belongs to', async () => {
    // Caused elsewhere — a price source reporting the bare market price is what
    // makes the energy tax required — which is why the message travels with the
    // answer instead of being worked out again in the panel (SPEC.md §14).
    const hass = fakeHass({
      config: sampleConfig({
        issues: {
          home: [
            {
              field: 'energy_tax_eur_kwh',
              code: 'required',
              message: 'De prijsbron levert de kale marktprijs.',
              severity: 'error',
            },
          ],
        },
      }),
    });
    const { tab } = await openHomeTab(hass);

    assert.deepEqual(forms(tab)[1].error, {
      energy_tax_eur_kwh: 'De prijsbron levert de kale marktprijs.',
    });
    // One mistake may not light up all three cards.
    assert.equal(forms(tab)[0].error, undefined);
    assert.equal(forms(tab)[2].error, undefined);
  });

  it('is filled from the stored configuration', async () => {
    const { tab } = await openHomeTab();

    assert.equal(forms(tab)[0].data.home_name, 'Mijn woning');
    assert.equal(forms(tab)[0].data.max_grid_power_w, 5750);
  });

  it('is not rebuilt when the panel state changes', async () => {
    const { panel, tab } = await openHomeTab();
    const before = forms(tab)[0];

    clickTab(panel, 'Overzicht');
    await settle();
    clickTab(panel, 'Woning');
    await settle();

    // The same element: re-creating it mid-edit would throw away whatever was
    // being typed (SPEC.md §9).
    assert.equal(forms(tab)[0], before);
  });

  it('shows the theoretical maximum and warns when it is exceeded', async () => {
    const { tab } = await openHomeTab();

    assert.ok(noticeTexts(tab).some((text) => text.includes('Theoretisch maximum')));

    change(tab, { max_grid_power_w: 99999 });

    const warning = noticeTexts(tab).find((text) => text.includes('theoretische'));
    assert.match(warning, /ligt boven het theoretische maximum/);
    // A warning, never a block (SPEC.md §8).
    assert.equal(findButton(tab, 'Opslaan').disabled, false);
  });

  it('keeps an edit from one card when another card changes', async () => {
    const { tab } = await openHomeTab();

    change(tab, { phases: 3 }, 0);
    change(tab, { contract_type: 'dynamic' }, 1);

    const hint = noticeTexts(tab).find((text) => text.includes('Theoretisch maximum'));
    assert.match(hint, /3 × 230 V × 25 A/);
  });

  it('sends the edit from every card, not only the last one touched', async () => {
    const sent = [];
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      sent.push(message);
      if (message.type === 'domotiapp_energy/home/update') {
        return { revision: 8, item: { ...message.home } };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { phases: 3 }, 0);
    change(tab, { contract_type: 'dynamic' }, 1);
    findButton(tab, 'Opslaan').click();
    await settle();

    const update = sent.find(
      (message) => message.type === 'domotiapp_energy/home/update',
    );
    assert.equal(update.home.phases, 3);
    assert.equal(update.home.contract_type, 'dynamic');
  });

  it('offers the other control levels but leaves them disabled', async () => {
    const { tab } = await openHomeTab();
    const controlForm = forms(tab)[3];

    assert.equal(controlForm.data.control_level, 'advice_only');
    assert.equal(controlForm.disabled, true);
    assert.ok(
      noticeTexts(tab).some((text) => text.includes('nog niet beschikbaar')),
    );
  });
});

describe('the save cycle', () => {
  it('keeps the save button disabled until something changed', async () => {
    const { tab } = await openHomeTab();

    assert.equal(findButton(tab, 'Opslaan').disabled, true);

    change(tab, { home_name: 'Woning Noord' });

    assert.equal(findButton(tab, 'Opslaan').disabled, false);
  });

  it('sends the edit with the revision it was filled in against', async () => {
    const sent = [];
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      sent.push(message);
      if (message.type === 'domotiapp_energy/home/update') {
        return { revision: 8, item: { ...message.home } };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { home_name: 'Woning Noord' });
    findButton(tab, 'Opslaan').click();
    await settle();

    const update = sent.find(
      (message) => message.type === 'domotiapp_energy/home/update',
    );
    assert.equal(update.expected_revision, 7);
    assert.equal(update.home.home_name, 'Woning Noord');
    // Fields the installer did not touch travel along unchanged: the backend
    // replaces the whole profile.
    assert.equal(update.home.max_grid_power_w, 5750);
  });

  it('sends a cleared field as null, not by leaving the key out', async () => {
    // The backend distinguishes an absent net_metering_until ("older file,
    // take the default") from an explicit null ("this home does not
    // net-meter"). Omitting the key would silently hand the default back and
    // undo the installer's choice on the next load (SPEC.md §16).
    const sent = [];
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      sent.push(message);
      if (message.type === 'domotiapp_energy/home/update') {
        return { revision: 8, item: { ...message.home } };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { net_metering_until: undefined }, 1);
    findButton(tab, 'Opslaan').click();
    await settle();

    const update = sent.find(
      (message) => message.type === 'domotiapp_energy/home/update',
    );
    assert.ok('net_metering_until' in update.home);
    assert.equal(update.home.net_metering_until, null);
  });

  it('locks the fields while saving and confirms only afterwards', async () => {
    let release;
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/home/update') {
        await new Promise((resolve) => {
          release = resolve;
        });
        return { revision: 8, item: { ...message.home } };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { home_name: 'Woning Noord' });
    findButton(tab, 'Opslaan').click();
    await settle();

    // In flight: everything locked, and nothing claiming success yet.
    assert.ok(editableForms(tab).every((form) => form.disabled));
    assert.equal(findButton(tab, 'Opslaan').disabled, true);
    assert.ok(noticeTexts(tab).some((text) => text.includes('Bezig met opslaan')));
    assert.ok(!noticeTexts(tab).some((text) => text.includes('opgeslagen.')));

    release();
    await settle();

    assert.ok(editableForms(tab).every((form) => !form.disabled));
    assert.ok(
      noticeTexts(tab).some((text) =>
        text.includes('De woninggegevens zijn opgeslagen'),
      ),
    );
  });

  it('shows a backend refusal in Dutch and keeps the form usable', async () => {
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/home/update') {
        throw { code: 'unauthorized', message: 'Unauthorized' };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { home_name: 'Woning Noord' });
    findButton(tab, 'Opslaan').click();
    await settle();

    assert.ok(noticeTexts(tab).some((text) => text.includes('geen rechten')));
    // The edit is still there to retry with.
    assert.equal(forms(tab)[0].data.home_name, 'Woning Noord');
    assert.ok(editableForms(tab).every((form) => !form.disabled));
  });

  it('reloads from the backend on a revision conflict', async () => {
    const theirs = sampleConfig({
      revision: 9,
      home: { home_name: 'Door iemand anders gewijzigd', phases: 3 },
    });
    const hass = fakeHass();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      if (message.type === 'domotiapp_energy/home/update') {
        // Exactly the shape the backend sends: the current configuration
        // travels with the refusal (SPEC.md §14).
        throw { code: 'revision_conflict', message: 'stale', revision: 9, config: theirs };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { home_name: 'Mijn wijziging' });
    findButton(tab, 'Opslaan').click();
    await settle();

    assert.ok(
      noticeTexts(tab).some((text) => text.includes('intussen ergens anders gewijzigd')),
    );
    // Reloaded, not overwritten: the other change survives and the stale edit
    // is gone rather than silently winning.
    assert.equal(forms(tab)[0].data.home_name, 'Door iemand anders gewijzigd');
    assert.equal(findButton(tab, 'Opslaan').disabled, true);
  });
});

describe('unsaved changes', () => {
  it('refuses to leave the tab and asks inside the page', async () => {
    const { panel, tab } = await openHomeTab();
    change(tab, { home_name: 'Woning Noord' });

    clickTab(panel, 'Overzicht');
    await settle();

    // Still on Woning, with the question next to the changes it is about.
    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-home');
    assert.ok(
      noticeTexts(tab).some((text) => text.includes('nog niet zijn opgeslagen')),
    );
  });

  it('lets the installer discard and continue', async () => {
    const { panel, tab } = await openHomeTab();
    change(tab, { home_name: 'Woning Noord' });
    clickTab(panel, 'Overzicht');
    await settle();

    findButton(tab, 'Verwerpen en verdergaan').click();
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-overview');
    assert.equal(forms(tab)[0].data.home_name, 'Mijn woning');
  });

  it('lets the installer stay and keep the changes', async () => {
    const { panel, tab } = await openHomeTab();
    change(tab, { home_name: 'Woning Noord' });
    clickTab(panel, 'Overzicht');
    await settle();

    findButton(tab, 'Hier blijven').click();
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-home');
    assert.equal(forms(tab)[0].data.home_name, 'Woning Noord');
  });

  it('leaves freely once the changes are discarded', async () => {
    const { panel, tab } = await openHomeTab();
    change(tab, { home_name: 'Woning Noord' });
    findButton(tab, 'Wijzigingen verwerpen').click();
    await settle();

    clickTab(panel, 'Overzicht');
    await settle();

    assert.equal(tabPanels(panel).filter(isVisible)[0].id, 'panel-overview');
  });
});

describe('the contract fields that apply', () => {
  /** The names the contract card is asking about right now. */
  function contractFields(tab) {
    return forms(tab)[1].schema.map((field) => field.name);
  }

  it('does not ask about a fixed tariff on a dynamic contract', async () => {
    const { tab } = await openHomeTab();

    // A fixed contract: the tariff is asked, the thresholds are not.
    assert.ok(contractFields(tab).includes('fixed_import_price_eur_kwh'));
    assert.ok(!contractFields(tab).includes('low_price_threshold_eur_kwh'));

    change(tab, { contract_type: 'dynamic' }, 1);

    // And the other way round. A question with no answer, kept on screen with
    // "alleen nodig bij een vast contract" underneath, is what this replaces.
    assert.ok(!contractFields(tab).includes('fixed_import_price_eur_kwh'));
    assert.ok(contractFields(tab).includes('low_price_threshold_eur_kwh'));
    assert.ok(contractFields(tab).includes('energy_tax_eur_kwh'));
  });

  it('keeps a hidden value and says that it is kept', async () => {
    const { tab } = await openHomeTab(
      fakeHass({
        config: sampleConfig({
          home: { ...sampleConfig().home, fixed_import_price_eur_kwh: 0.3 },
        }),
      }),
    );

    change(tab, { contract_type: 'dynamic' }, 1);

    // Unlike a device type, a contract type flips back and forth: forgetting
    // the tariff would mean retyping it on the way back.
    assert.ok(
      noticeTexts(tab).some((text) => text.includes('blijven bewaard')),
      'the tab has to say that the value is kept',
    );
  });

  /** A home with both contracts filled in, which is the case that broke. */
  function bothContractsFilled() {
    return fakeHass({
      config: sampleConfig({
        home: {
          ...sampleConfig().home,
          contract_type: 'fixed',
          fixed_import_price_eur_kwh: 0.3,
          energy_tax_eur_kwh: 0.1088,
          supplier_markup_eur_kwh: 0.02,
          vat_percent: 21,
          low_price_threshold_eur_kwh: 0.15,
          high_price_threshold_eur_kwh: 0.35,
        },
      }),
    });
  }

  it('keeps the other contract through a round trip', async () => {
    const { tab } = await openHomeTab(bothContractsFilled());

    // Away and back. The card is only ever handed the fields of the contract
    // in force, so everything belonging to the other one is absent from every
    // payload it emits — and merging that against the full schema used to
    // clear those fields before they had ever been on screen.
    change(tab, { contract_type: 'dynamic' }, 1);
    change(tab, { contract_type: 'fixed' }, 1);

    const contract = forms(tab)[1];
    assert.equal(
      contract.data.fixed_import_price_eur_kwh,
      0.3,
      'the fixed tariff has to survive a trip through the dynamic contract',
    );
  });

  it('keeps the dynamic composition on the very first switch', async () => {
    const { tab } = await openHomeTab(bothContractsFilled());

    change(tab, { contract_type: 'dynamic' }, 1);

    // These are the fields a fixed contract never shows, so they were the ones
    // wiped by the switch that was supposed to reveal them.
    const contract = forms(tab)[1];
    assert.equal(contract.data.energy_tax_eur_kwh, 0.1088);
    assert.equal(contract.data.supplier_markup_eur_kwh, 0.02);
    assert.equal(contract.data.vat_percent, 21);
    assert.equal(contract.data.low_price_threshold_eur_kwh, 0.15);
    assert.equal(contract.data.high_price_threshold_eur_kwh, 0.35);
  });

  it('does not write the other contract away as null', async () => {
    const sent = [];
    const hass = bothContractsFilled();
    const original = hass.callWS;
    hass.callWS = async (message) => {
      sent.push(message);
      if (message.type === 'domotiapp_energy/home/update') {
        return { revision: 8, item: { ...message.home }, issues: {} };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { contract_type: 'dynamic' }, 1);
    findButton(tab, 'Opslaan').click();
    await settle();

    // payload() sends null for anything missing from the draft, so a value
    // cleared by the switch was not merely invisible: saving wrote the loss to
    // storage, while the notice underneath said the values were kept.
    const update = sent.find(
      (message) => message.type === 'domotiapp_energy/home/update',
    );
    assert.equal(update.home.fixed_import_price_eur_kwh, 0.3);
    assert.equal(update.home.energy_tax_eur_kwh, 0.1088);
    assert.equal(update.home.supplier_markup_eur_kwh, 0.02);
    assert.equal(update.home.vat_percent, 21);
  });

  it('still sends the value of the contract that is not in force', async () => {
    const sent = [];
    const hass = fakeHass({
      config: sampleConfig({
        home: { ...sampleConfig().home, fixed_import_price_eur_kwh: 0.3 },
      }),
    });
    const original = hass.callWS;
    hass.callWS = async (message) => {
      sent.push(message);
      if (message.type === 'domotiapp_energy/home/update') {
        return { revision: 8, item: { ...message.home }, issues: {} };
      }
      return original(message);
    };

    const { tab } = await openHomeTab(hass);
    change(tab, { contract_type: 'dynamic' }, 1);
    findButton(tab, 'Opslaan').click();
    await settle();

    const update = sent.find(
      (message) => message.type === 'domotiapp_energy/home/update',
    );
    assert.equal(update.home.contract_type, 'dynamic');
    // Hidden, not dropped.
    assert.equal(update.home.fixed_import_price_eur_kwh, 0.3);
  });
});
