sub init()
  m.top.functionName = "runTask"
end sub

sub runTask()
  out = {}
  cmd = m.top.command
  if cmd = "item"
    out = fetchOne(m.top.itemId)
  else if cmd = "playing"
    out = reportPlayback("Playing")
  else if cmd = "progress"
    out = reportPlayback("Playing/Progress")
  else if cmd = "stopped"
    out = reportPlayback("Playing/Stopped")
  else if cmd = "displayProfile"
    out = postDisplayProfile()
  else
    out = fetchList()
  end if
  ' FormatJson is the reliable Task → render bridge
  m.top.resultJson = FormatJson(out)
end sub

function trimSlash(base as string) as string
  if base = invalid then return ""
  b = base.Trim()
  while Len(b) > 0 and Right(b, 1) = "/"
    b = Left(b, Len(b) - 1)
  end while
  return b
end function

function authHeader() as string
  ' Token in Authorization is what Jellyfin uses to bind Client/Device into /Sessions
  return "MediaBrowser Client=""JellyFlam3"", Device=""Roku"", DeviceId=""jellyflam3-roku"", Version=""1.0.27"", Token=""" + m.top.apiKey + """"
end function

' Lab-verified HLS remux path: prefer main.m3u8 + AudioCodec=aac.
' Avoid master.m3u8 — Jellyfin 10.11 may inject AudioCodec=m3u8 → ffmpeg exit 8.
function hlsStreamUrl(base as string, itemId as string) as string
  return base + "/Videos/" + itemId + "/main.m3u8?MediaSourceId=" + itemId + "&api_key=" + m.top.apiKey + "&AudioCodec=aac"
end function

function mp4StreamUrl(base as string, itemId as string) as string
  return base + "/Videos/" + itemId + "/stream.mp4?Static=true&api_key=" + m.top.apiKey
end function

function httpRequest(method as string, url as string, body as string) as object
  xfer = CreateObject("roUrlTransfer")
  port = CreateObject("roMessagePort")
  xfer.SetPort(port)
  xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
  xfer.InitClientCertificates()
  xfer.EnablePeerVerification(false)
  xfer.EnableHostVerification(false)
  xfer.RetainBodyOnError(true)
  xfer.AddHeader("Accept", "application/json")
  xfer.AddHeader("Authorization", authHeader())
  xfer.AddHeader("X-Emby-Authorization", authHeader())
  if method = "POST"
    xfer.AddHeader("Content-Type", "application/json")
  end if
  ok = xfer.SetUrl(url)
  if ok <> true
    return { code: -1, body: "", reason: "SetUrl failed (bad URL?)" }
  end if
  started = false
  if method = "POST"
    started = xfer.AsyncPostFromString(body)
  else
    started = xfer.AsyncGetToString()
  end if
  if started <> true
    return { code: -1, body: "", reason: method + " failed to start" }
  end if

  msg = wait(15000, port)
  if msg = invalid
    xfer.AsyncCancel()
    return { code: -1, body: "", reason: "timeout 15s — Roku cannot reach " + urlHost(url) }
  end if
  if type(msg) <> "roUrlEvent"
    return { code: -1, body: "", reason: "unexpected event " + type(msg) }
  end if
  code = msg.GetResponseCode()
  respBody = msg.GetString()
  reason = msg.GetFailureReason()
  if reason = invalid then reason = ""
  return { code: code, body: respBody, reason: reason }
end function

function httpGet(url as string) as object
  return httpRequest("GET", url, "")
end function

' POST profile to Pi display_profile_sink (no Jellyfin auth).
function httpPostJson(url as string, body as string, sinkToken as string) as object
  xfer = CreateObject("roUrlTransfer")
  port = CreateObject("roMessagePort")
  xfer.SetPort(port)
  xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
  xfer.InitClientCertificates()
  xfer.EnablePeerVerification(false)
  xfer.EnableHostVerification(false)
  xfer.RetainBodyOnError(true)
  xfer.AddHeader("Accept", "application/json")
  xfer.AddHeader("Content-Type", "application/json")
  if sinkToken <> invalid and sinkToken <> ""
    xfer.AddHeader("X-JellyFlam3-Token", sinkToken)
  end if
  ok = xfer.SetUrl(url)
  if ok <> true
    return { code: -1, body: "", reason: "SetUrl failed (bad URL?)" }
  end if
  started = xfer.AsyncPostFromString(body)
  if started <> true
    return { code: -1, body: "", reason: "POST failed to start" }
  end if
  msg = wait(15000, port)
  if msg = invalid
    xfer.AsyncCancel()
    return { code: -1, body: "", reason: "timeout 15s — cannot reach display sink" }
  end if
  if type(msg) <> "roUrlEvent"
    return { code: -1, body: "", reason: "unexpected event " + type(msg) }
  end if
  code = msg.GetResponseCode()
  respBody = msg.GetString()
  reason = msg.GetFailureReason()
  if reason = invalid then reason = ""
  return { code: code, body: respBody, reason: reason }
end function

function postDisplayProfile() as object
  sink = m.top.displaySinkUrl
  if sink = invalid then sink = ""
  sink = trimSlash(sink)
  body = m.top.profileJson
  if body = invalid then body = ""
  if sink = "" then return { error: "displaySinkUrl not set", ok: false }
  if body = "" then return { error: "profileJson empty", ok: false }
  token = ""
  if m.top.sinkToken <> invalid then token = m.top.sinkToken
  url = sink + "/v1/display-profiles"
  resp = httpPostJson(url, body, token)
  if resp.code <> 200
    detail = "HTTP " + resp.code.toStr()
    if resp.reason <> invalid and resp.reason <> "" then detail = detail + ": " + resp.reason
    if resp.body <> invalid and resp.body <> "" then detail = detail + " " + Left(resp.body, 120)
    return { ok: false, error: "display sink failed — " + detail, debugUrl: url }
  end if
  parsed = invalid
  if resp.body <> invalid and resp.body <> ""
    parsed = ParseJson(resp.body)
  end if
  if parsed = invalid then return { ok: true, raw: resp.body }
  parsed.ok = true
  return parsed
end function

sub registerSession(base as string)
  ' Best-effort: advertise Client=JellyFlam3 Device=Roku for idle-gate matching
  q = Chr(34)
  body = "{" + q + "PlayableMediaTypes" + q + ":[" + q + "Video" + q + "]," + q + "SupportedCommands" + q + ":[]," + q + "SupportsMediaControl" + q + ":false," + q + "SupportsPersistentIdentifier" + q + ":true}"
  httpRequest("POST", base + "/Sessions/Capabilities/Full", body)
end sub

function urlHost(url as string) as string
  ' crude host for error text
  u = url
  if Left(u, 7) = "http://" then u = Mid(u, 8)
  if Left(u, 8) = "https://" then u = Mid(u, 9)
  slash = Instr(1, u, "/")
  if slash > 0 then u = Left(u, slash - 1)
  return u
end function

function flockItemFields() as string
  return "Overview,Tags,RunTimeTicks,PrimaryImageAspectRatio,ImageTags,Path"
end function

function fetchRawItems(base as string, parentId as string, limit as integer) as object
  ' Do not pass Tags= to Jellyfin — comma lists return an empty flock (AND/strict).
  path = base + "/Users/" + m.top.userId + "/Items?IncludeItemTypes=Movie,Video&Recursive=true&Fields=" + flockItemFields() + "&Limit=" + limit.toStr()
  if parentId <> invalid and parentId <> ""
    path = path + "&ParentId=" + parentId
  end if
  resp = httpGet(path)
  if resp.code <> 200
    detail = "HTTP " + resp.code.toStr()
    if resp.reason <> invalid and resp.reason <> "" then detail = detail + ": " + resp.reason
    return { error: "Items failed — " + detail, debugUrl: path, items: [] }
  end if
  data = ParseJson(resp.body)
  if data = invalid then return { error: "Items JSON error", debugUrl: path, items: [] }
  raw = data.Items
  if raw = invalid then raw = []
  return { items: raw, debugUrl: path }
end function

' Jellyfin 10.x: ParentId=library root + IncludeItemTypes=Video&Recursive=true often
' returns only a partial flock (or none) when videos live under by-generation/ children.
function fetchItemsViaChildFolders(base as string, libraryId as string, limit as integer) as object
  fpath = base + "/Users/" + m.top.userId + "/Items?IncludeItemTypes=Folder&Recursive=false&ParentId=" + libraryId + "&Limit=50"
  resp = httpGet(fpath)
  if resp.code <> 200 then return []
  data = ParseJson(resp.body)
  if data = invalid or data.Items = invalid then return []
  merged = []
  for each folder in data.Items
    if merged.count() >= limit then exit for
    fid = folder.Id
    if fid = invalid or fid = "" then continue for
    remain = limit - merged.count()
    batch = fetchRawItems(base, fid, remain)
    if batch.error <> invalid then continue for
    batchItems = batch.items
    if batchItems = invalid then continue for
    for each it in batchItems
      merged.push(it)
      if merged.count() >= limit then exit for
    end for
  end for
  return merged
end function

' Prefer nested folder hits first, then flat ParentId hits; dedupe by Id.
function mergeItemsById(primary as object, extra as object, limit as integer) as object
  seen = {}
  out = []
  if primary <> invalid
    for each it in primary
      if out.count() >= limit then return out
      if it = invalid then continue for
      id = it.Id
      if id = invalid or id = "" then continue for
      if seen.DoesExist(id) then continue for
      seen.AddReplace(id, true)
      out.push(it)
    end for
  end if
  if extra <> invalid
    for each it in extra
      if out.count() >= limit then return out
      if it = invalid then continue for
      id = it.Id
      if id = invalid or id = "" then continue for
      if seen.DoesExist(id) then continue for
      seen.AddReplace(id, true)
      out.push(it)
    end for
  end if
  return out
end function

function fetchList() as object
  base = trimSlash(m.top.baseUrl)
  if base = "" then return { error: "baseUrl not set" }
  if m.top.apiKey = invalid or m.top.apiKey = "" then return { error: "apiKey not set" }
  if m.top.userId = invalid or m.top.userId = "" then return { error: "userId not set" }

  registerSession(base)

  limit = 200
  libId = ""
  if m.top.libraryId <> invalid and m.top.libraryId <> "" then libId = m.top.libraryId

  fetched = fetchRawItems(base, libId, limit)
  if fetched.error <> invalid
    return { error: fetched.error, debugUrl: fetched.debugUrl }
  end if
  raw = fetched.items
  ' Always walk child folders when libraryId is set — empty-only fallback misses
  ' partial flat hits (lab: 1 of 6 sheep under by-generation/).
  if libId <> ""
    nested = fetchItemsViaChildFolders(base, libId, limit)
    raw = mergeItemsById(nested, raw, limit)
  end if
  ' Commercial filtering is client-side via isCommercialSafe() below.

  items = []
  for each it in raw
    if m.top.commercialMode = true
      if isCommercialSafe(it) then items.push(mapItem(it, base))
    else
      items.push(mapItem(it, base))
    end if
  end for
  return { items: items, count: items.count() }
end function

function isCommercialSafe(it as object) as boolean
  if it.Tags = invalid then return false
  for each t in it.Tags
    tl = LCase(t)
    if tl = "cc-by-nc" or tl = "cc-by-nc-sa" or Instr(1, tl, "by-nc") > 0
      return false
    end if
    if tl = "cc-by" or tl = "cc0" or tl = "public-domain" or tl = "pd"
      return true
    end if
  end for
  return false
end function

function formatDurationLabel(sec as integer) as string
  if sec <= 0 then return ""
  return sec.toStr() + "s"
end function

function tagsList(it as object) as object
  tags = []
  if it.Tags <> invalid
    for each t in it.Tags
      if t <> invalid and t <> "" then tags.push(t)
    end for
  end if
  return tags
end function

' Derive browse metadata from Tags, Name/Path, Overview.
function extractMeta(it as object) as object
  tags = tagsList(it)
  generation = ""
  license = ""
  pedigree = ""
  sheepId = ""

  for each t in tags
    tl = LCase(t)
    if Left(tl, 11) = "generation-"
      generation = Mid(t, 12)
    else if Left(tl, 6) = "sheep-"
      sheepId = Mid(t, 7)
    else if tl = "cc-by-nc" or tl = "cc-by-nc-sa"
      license = "cc-by-nc"
    else if tl = "cc-by" or tl = "cc-by-sa"
      if license = "" then license = "cc-by"
    else if tl = "cc0" or tl = "public-domain" or tl = "pd"
      if license = "" then license = tl
    else if tl = "local_pedigree" or tl = "pedigree" or Instr(1, tl, "pedigree") > 0
      pedigree = t
    else if tl = "human" or tl = "brood"
      if pedigree = "" then pedigree = t
    end if
  end for

  ' Filename / Name fallback: electricsheep.247.00600
  nameProbe = ""
  if it.Name <> invalid then nameProbe = it.Name
  if it.Path <> invalid and it.Path <> "" then nameProbe = nameProbe + " " + it.Path
  if generation = "" or sheepId = ""
    ' BrightScript has no regex — scan for electricsheep.GEN.ID
    low = LCase(nameProbe)
    marker = "electricsheep."
    idx = Instr(1, low, marker)
    if idx > 0
      rest = Mid(nameProbe, idx + Len(marker))
      ' rest like 247.00600.mp4 or 247.00600
      parts = rest.Tokenize(".")
      if parts.count() >= 2
        if generation = "" then generation = parts[0]
        if sheepId = "" then sheepId = parts[1]
      end if
    end if
  end if

  ' Overview lines: "License: cc-by-nc"
  if license = "" and it.Overview <> invalid
    ov = it.Overview
    licKey = "License:"
    li = Instr(1, ov, licKey)
    if li = 0 then li = Instr(1, ov, "license:")
    if li > 0
      frag = Mid(ov, li + Len(licKey)).Trim()
      ' first token / line
      nl = Instr(1, frag, Chr(10))
      if nl > 0 then frag = Left(frag, nl - 1)
      frag = frag.Trim()
      sp = Instr(1, frag, " ")
      if sp > 0 then frag = Left(frag, sp - 1)
      if frag <> "" then license = LCase(frag)
    end if
  end if

  return {
    generation: generation
    license: license
    pedigree: pedigree
    sheepId: sheepId
  }
end function

function buildMetaLine(durationLabel as string, meta as object) as string
  bits = []
  if durationLabel <> "" then bits.push(durationLabel)
  if meta.generation <> invalid and meta.generation <> ""
    bits.push("gen " + meta.generation)
  end if
  if meta.license <> invalid and meta.license <> ""
    bits.push(meta.license)
  end if
  if meta.pedigree <> invalid and meta.pedigree <> ""
    bits.push(meta.pedigree)
  end if
  if bits.count() = 0 then return ""
  line = bits[0]
  i = 1
  while i < bits.count()
    line = line + " · " + bits[i]
    i = i + 1
  end while
  return line
end function

function mapItem(it as object, base as string) as object
  ticks = 0
  if it.RunTimeTicks <> invalid then ticks = it.RunTimeTicks
  lengthSec = Int(ticks / 10000000)
  durationLabel = formatDurationLabel(lengthSec)
  ' Only set poster URL when Jellyfin has a Primary ImageTag (else FlockItem placeholder).
  poster = ""
  hasPrimary = false
  if it.ImageTags <> invalid and it.ImageTags.Primary <> invalid and it.ImageTags.Primary <> ""
    hasPrimary = true
  end if
  if hasPrimary = true and it.Id <> invalid
    poster = base + "/Items/" + it.Id + "/Images/Primary?maxWidth=320&api_key=" + m.top.apiKey
  end if
  desc = ""
  if it.Overview <> invalid then desc = it.Overview
  title = "Untitled"
  if it.Name <> invalid then title = it.Name
  meta = extractMeta(it)
  metaLine = buildMetaLine(durationLabel, meta)
  hls = hlsStreamUrl(base, it.Id)
  mp4 = mp4StreamUrl(base, it.Id)
  mediaPath = ""
  if it.Path <> invalid then mediaPath = it.Path
  ' url stays HLS for deep-link/list compatibility; PlayerScreen picks via streamMode.
  return {
    id: it.Id
    title: title
    description: desc
    hdPosterUrl: poster
    hasPrimary: hasPrimary
    url: hls
    hlsUrl: hls
    mp4Url: mp4
    streamFormat: "hls"
    length: lengthSec
    durationLabel: durationLabel
    generation: meta.generation
    license: meta.license
    pedigree: meta.pedigree
    sheepId: meta.sheepId
    metaLine: metaLine
    mediaPath: mediaPath
  }
end function

function fetchOne(itemId as string) as object
  base = trimSlash(m.top.baseUrl)
  if itemId = invalid or itemId = "" then return { error: "empty itemId" }
  if m.top.userId = invalid or m.top.userId = "" then return { error: "userId not set" }
  if m.top.apiKey = invalid or m.top.apiKey = "" then return { error: "apiKey not set" }

  registerSession(base)

  path = base + "/Users/" + m.top.userId + "/Items/" + itemId + "?Fields=Overview,Tags,RunTimeTicks,ImageTags,Path"
  resp = httpGet(path)
  if resp.code <> 200
    hls = hlsStreamUrl(base, itemId)
    return {
      items: [{
        id: itemId
        title: itemId
        description: ""
        hdPosterUrl: ""
        url: hls
        hlsUrl: hls
        mp4Url: mp4StreamUrl(base, itemId)
        streamFormat: "hls"
        length: 23
      }]
      count: 1
    }
  end if
  data = ParseJson(resp.body)
  if data = invalid then return { error: "item JSON error" }
  return { items: [mapItem(data, base)], count: 1 }
end function

function reportPlayback(pathSuffix as string) as object
  base = trimSlash(m.top.baseUrl)
  itemId = m.top.itemId
  if base = "" then return { error: "baseUrl not set" }
  if itemId = invalid or itemId = "" then return { error: "itemId not set" }
  if m.top.apiKey = invalid or m.top.apiKey = "" then return { error: "apiKey not set" }

  ticks = 0
  if m.top.positionTicks <> invalid then ticks = m.top.positionTicks
  ' HLS remux → DirectStream; Static MP4 → DirectPlay (idle-gate / Sessions accuracy)
  playMethod = "DirectStream"
  if m.top.playMethod <> invalid and m.top.playMethod <> ""
    playMethod = m.top.playMethod
  end if
  q = Chr(34)
  body = "{"
  body = body + q + "ItemId" + q + ":" + q + itemId + q + ","
  body = body + q + "MediaSourceId" + q + ":" + q + itemId + q + ","
  body = body + q + "PositionTicks" + q + ":" + ticks.toStr() + ","
  body = body + q + "IsPaused" + q + ":false,"
  body = body + q + "IsMuted" + q + ":false,"
  body = body + q + "CanSeek" + q + ":true,"
  body = body + q + "PlayMethod" + q + ":" + q + playMethod + q + ","
  body = body + q + "RepeatMode" + q + ":" + q + "RepeatAll" + q
  body = body + "}"
  resp = httpRequest("POST", base + "/Sessions/" + pathSuffix, body)
  if resp.code < 200 or resp.code >= 300
    detail = "HTTP " + resp.code.toStr()
    if resp.reason <> invalid and resp.reason <> "" then detail = detail + ": " + resp.reason
    return { error: "Sessions/" + pathSuffix + " failed — " + detail, code: resp.code }
  end if
  return { ok: true, code: resp.code, path: pathSuffix }
end function
