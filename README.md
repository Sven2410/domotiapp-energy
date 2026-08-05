# DomotiApp Energy

A manually configured energy coach for Home Assistant.

**Status: Work in progress — 0.1.0 in development.**

DomotiApp Energy turns the energy sources and appliances you connect by hand into an
energy summary, a data completeness score, an energy score, advice, and grid peak
warnings. Everything is calculated locally: no cloud service, no external API, no
account, and no AI provider.

DomotiApp Energy does not automatically discover, select, or control devices in version 0.1.0.

The DomotiApp Energy Score is a local advisory indicator and not a certified energy-efficiency rating.

## Troubleshooting

### Removing the integration keeps the energy configuration

Deleting DomotiApp Energy from *Settings → Devices & services* removes the entities and
the device, but **not** the home profile, energy sources, appliances, preferences and
logbook. Those live in `.storage/domotiapp_energy.config` inside your Home Assistant
configuration directory, and adding the integration again picks them straight back up.

That is deliberate: an accidental removal, or a reinstall, should not cost you a full
re-entry of every source and appliance. Home Assistant does not let an integration put a
message in the removal dialog, so the only notice is a line in the Home Assistant log
when you remove it.

To start over with an empty configuration:

1. remove the integration in *Settings → Devices & services*;
2. stop Home Assistant;
3. delete `.storage/domotiapp_energy.config` from the configuration directory;
4. start Home Assistant and add the integration again.

Stopping first matters: Home Assistant caches `.storage` files in memory and can write
the old contents back over your deletion.

## Documentation

The full README — installation, configuration, the exact list of generated entity IDs,
services, limitations, troubleshooting and development instructions — is written in the
final phase of the initial implementation. Until then, `SPEC.md` in this repository is
the authoritative description of the intended behaviour.

## License

MIT — see [LICENSE](LICENSE).
