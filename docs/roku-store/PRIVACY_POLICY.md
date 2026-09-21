# JellyFlam3 Privacy Policy

**Effective date:** 20 September 2026  
**Product:** JellyFlam3 (Roku video channel) and, where installed, JellyFlam3 Dreams (Roku screensaver)  
**Publisher:** JellyFlam3 Server contributors ([source repository](https://github.com/awuehler/jellyflam3-server))

This policy explains what the JellyFlam3 Roku applications store on the device and what they send over the network. It is written for Roku Channel Store registration and for people who install the channel. It is not legal advice.

JellyFlam3 is a **client** for a **Jellyfin media server that you (or your household operator) run**, typically on a Raspberry Pi on your local network. We do not operate a JellyFlam3 cloud account, advertising network, or analytics service for this channel.

## 1. Who is responsible

- **You / your household operator** control the Jellyfin library, API keys, and any other services on that server (the “Server”). That operator is responsible for the media and for any logs those services keep.
- **The JellyFlam3 channel** stores connection settings on the Roku and talks only to the Server URL you configure (and, optionally, a companion service on the same host used for display hints and votes).
- **Roku** may collect platform data under [Roku’s privacy policy](https://docs.roku.com/legal/privacy). This policy does not cover Roku, Inc.

## 2. Data stored on the Roku

The channel uses Roku’s on-device registry (section `JellyFlam3`). Typical keys include:

| Kind | Examples | Purpose |
|---|---|---|
| Connection | Jellyfin base URL, API key, user id, library id | Load your flock and play streams |
| Preferences | commercial-safe filter, stream mode (MP4/HLS), title mode, screensaver fade/dwell | Playback and captions |
| Optional companion | display-sink URL and token | TV display probe and like/love votes |

That data stays **on the device** until you change Settings, uninstall the channel, or factory-reset the Roku. Furnace-built sideload packages may pre-fill connection keys on first launch if the registry is empty. We do not receive a copy of the registry.

## 3. Data sent over the network

Traffic goes to **the Server you configured**, not to a JellyFlam3-operated backend.

| Activity | Destination | What is sent |
|---|---|---|
| Browse and play | Your Jellyfin URL (often `http://<your-lan-ip>:8096`) | API key (authorization), library queries, image and video URLs |
| Playback state (VoD) | Same Jellyfin | Session / Playing progress so the Server can pause rendering while the TV plays |
| Optional “Fetch TV display” | Companion service on the Server host (default port 8791) | Device/display facts (model, resolution, HDR flags, channel client id) plus the sink token |
| Optional like / love (VoD; not the Roku screensaver) | Same companion service | Sheep identifier and vote kind; token required |

Deep-link / voice Direct to Play may include a `contentId` and `mediaType` supplied by Roku or ECP. Those values are used only to select an item on **your** Server.

If you point the channel at a Server on the public internet or a VPN, the same categories of data leave the LAN. That is under your control.

## 4. What we do not collect

The publisher of this Channel Store listing does **not**:

- Create user accounts for JellyFlam3
- Run ads, attribution SDKs, or third-party analytics in the channel
- Sell personal information
- Require an email address, payment card, or social login inside the app

## 5. Children

JellyFlam3 is a homelab / ambient-media client. It is **not directed at children under 13**. Do not configure it with an account or library intended for children unless you are the parent or operator of that Server and accept responsibility for that library.

## 6. Your choices

- Edit or clear credentials in channel Settings.
- Uninstall the channel or perform a Roku factory reset to drop registry keys.
- Disable votes and display-sink by not setting a sink token / URL.
- Restrict the Server to your LAN or VPN.

## 7. Third parties

The Server software may include Jellyfin, ffmpeg, flam3, and related open-source components. Their operators (you) and their upstream projects have their own terms. JellyFlam3 is not affiliated with Roku, Inc., Jellyfin, or Spotworks LLC / Electric Sheep. See [NOTICE](https://github.com/awuehler/jellyflam3-server/blob/master/NOTICE).

## 8. International users

The channel does not host a publisher-side database of viewers. Processing happens on the Roku and on the Server you choose. If that Server is in another country, your operator’s rules apply there.

## 9. Changes

We may update this policy in the repository. The effective date at the top will change. Continued use after an update means you accept the revised policy.

## 10. Contact

Privacy questions: open an issue at [github.com/awuehler/jellyflam3-server/issues](https://github.com/awuehler/jellyflam3-server/issues) or use the support contacts listed in [SUPPORT.md](SUPPORT.md).
