# JellyFlam3 Support Contact

**Effective date:** 20 September 2026  
**Channel name:** JellyFlam3  
**Learn more:** https://github.com/awuehler/jellyflam3-server

This page is the **customer support URL** for Roku Channel Store registration ([app publishing — support information](https://developer.roku.com/dev/docs/channel-publishing-guide)).

## End-user support (public)

| Channel | How to reach us |
|---|---|
| **Primary** | GitHub Issues: https://github.com/awuehler/jellyflam3-server/issues |
| **Docs** | [User guide and runbook](https://github.com/awuehler/jellyflam3-server/blob/master/docs/USER_GUIDE_AND_RUNBOOK.md) · [Fridge card](https://github.com/awuehler/jellyflam3-server/blob/master/docs/FRIDGE_CARD.md) |
| **Email / phone** | Use the address and number on the **Roku developer account** that published this channel (entered in Developer Dashboard → Support Information). They are not duplicated here so they cannot rot in git. |

Support is **best-effort**, in English, via GitHub. There is no SLA, 24/7 desk, or in-app chat.

## What we can help with

- Channel will not list the flock or play a sheep when the Server URL is a LAN Jellyfin
- Settings (URL, API key, user id, library id), commercial-safe filter, stream mode, votes
- Sideload vs Channel Store install, one developer slot vs private channel
- Pointers into the public documentation

## What we cannot do

- Access or reset **your** Raspberry Pi, Jellyfin, Wi-Fi, or API key
- Recover a lost `DISPLAY_SINK_TOKEN` or registry
- License Electric Sheep / Spotworks content or brand art
- Support unofficial builds, forks, or modified packages
- Provide Roku platform support (device firmware, billing) — use [Roku customer support](https://support.roku.com/)

## Before you write

1. Confirm `baseUrl` is the Pi’s **LAN IP** (for example `http://192.168.x.x:8096`), not `127.0.0.1`.
2. Confirm the TV and the Pi are on the same network (or a VPN you intend to use).
3. Note channel version (Settings / ECP `dev` version) and Roku software version.
4. **Do not paste API keys, sink tokens, or `secrets.env` into a public issue.**

## Developer Dashboard paste-box

Roku requires customer support **URL, email, and phone**. Suggested mapping:

| Field | Value |
|---|---|
| Customer support URL | `https://github.com/awuehler/jellyflam3-server/blob/master/docs/roku-store/SUPPORT.md` |
| Customer support email | Developer-account email (same as Channel Store publisher) |
| Customer support phone | Developer-account phone, with country code |
| Administrative contact | Same publisher name / email / phone unless you designate otherwise |
| Technical contact | Same, or a second operator you control |
| Preferred / learn more URL | `https://github.com/awuehler/jellyflam3-server` |

## Related policies

- [Privacy Policy](PRIVACY_POLICY.md)
- [Terms of Use](TERMS_OF_USE.md)
