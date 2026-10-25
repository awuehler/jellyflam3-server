sub init()
  m.top.functionName = "runTask"
end sub

sub runTask()
  m.dnsRetryUsed = false
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
  else if cmd = "reach"
    out = probeReach()
  else if cmd = "displayProfile"
    out = postDisplayProfile()
  else if cmd = "sheepVote"
    out = postSheepVote()
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

' Same id Fetch TV display stores: this channel's client id, else the model, else a placeholder.
' A shared DeviceId makes every TV one Jellyfin session.
function channelDeviceId() as string
  if m.channelDeviceId <> invalid and m.channelDeviceId <> "" then return m.channelDeviceId
  id = ""
  di = CreateObject("roDeviceInfo")
  if di <> invalid
    cid = di.GetChannelClientId()
    if cid <> invalid and cid <> "" then id = cid.toStr()
    if id = ""
      model = di.GetModel()
      if model <> invalid and model <> "" then id = "roku-" + model.toStr()
    end if
  end if
  if id = "" then id = "roku-unknown"
  m.channelDeviceId = id
  return id
end function

function authHeader() as string
  ' Token in Authorization is what Jellyfin uses to bind Client/Device into /Sessions.
  ' DeviceId is per TV so two screens stay two sessions. Client stays JellyFlam3.
  return "MediaBrowser Client=""JellyFlam3"", Device=""Roku"", DeviceId=""" + channelDeviceId() + """, Version=""1.0.67"", Token=""" + m.top.apiKey + """"
end function

' Lab-verified HLS remux path: prefer main.m3u8 + AudioCodec=aac.
' Avoid master.m3u8 — Jellyfin 10.11 may inject AudioCodec=m3u8 → ffmpeg exit 8.
' Jellyfin 12.0+ rejects the legacy api_key query parameter on this route.
' The Video node cannot send an Authorization header, so the playlist carries ApiKey.
function hlsStreamUrl(base as string, itemId as string) as string
  return base + "/Videos/" + itemId + "/main.m3u8?MediaSourceId=" + itemId + "&ApiKey=" + m.top.apiKey + "&AudioCodec=aac"
end function

function mp4StreamUrl(base as string, itemId as string) as string
  return base + "/Videos/" + itemId + "/stream.mp4?Static=true&api_key=" + m.top.apiKey
end function

function httpRequest(method as string, url as string, body as string) as object
  return httpRequestWait(method, url, body, 15000)
end function

function httpRequestWait(method as string, url as string, body as string, timeoutMs as integer) as object
  xfer = CreateObject("roUrlTransfer")
  port = CreateObject("roMessagePort")
  xfer.SetPort(port)
  xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
  xfer.EnablePeerVerification(true)
  xfer.EnableHostVerification(true)
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

  waitMs = timeoutMs
  if waitMs < 1000 then waitMs = 1000
  msg = wait(waitMs, port)
  if msg = invalid
    xfer.AsyncCancel()
    secs = Int(waitMs / 1000)
    if secs < 1 then secs = 1
    return { code: -1, body: "", reason: "timeout " + secs.toStr() + "s — Roku cannot reach " + urlHost(url) }
  end if
  if type(msg) <> "roUrlEvent"
    return { code: -1, body: "", reason: "unexpected event " + type(msg) }
  end if
  code = msg.GetResponseCode()
  respBody = msg.GetString()
  reason = msg.GetFailureReason()
  if reason = invalid then reason = ""
  ' A cold Roku resolver can miss a hostname once. One pause covers that
  ' without turning every later failure into a second wait.
  if m.dnsRetryUsed <> true and isDnsLookupFailure(reason)
    m.dnsRetryUsed = true
    Sleep(3000)
    return httpRequestWait(method, url, body, timeoutMs)
  end if
  return { code: code, body: respBody, reason: reason }
end function

function isDnsLookupFailure(reason as string) as boolean
  if reason = invalid or reason = "" then return false
  return Instr(1, LCase(reason), "domain name not found") > 0
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
  xfer.EnablePeerVerification(true)
  xfer.EnableHostVerification(true)
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

function postSheepVote() as object
  sink = m.top.displaySinkUrl
  if sink = invalid then sink = ""
  sink = trimSlash(sink)
  body = m.top.voteJson
  if body = invalid then body = ""
  if sink = "" then return { error: "displaySinkUrl not set", ok: false }
  if body = "" then return { error: "voteJson empty", ok: false }
  token = ""
  if m.top.sinkToken <> invalid then token = m.top.sinkToken
  url = sink + "/v1/sheep-votes"
  resp = httpPostJson(url, body, token)
  if resp.code <> 200
    detail = "HTTP " + resp.code.toStr()
    if resp.reason <> invalid and resp.reason <> "" then detail = detail + ": " + resp.reason
    if resp.body <> invalid and resp.body <> "" then detail = detail + " " + Left(resp.body, 120)
    return { ok: false, error: "sheep vote sink failed — " + detail, debugUrl: url }
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
  ' Best-effort idle-gate advertise. Do not wait — a dead Pi must not add a
  ' second 15s before the Items GET (cold-fail used to take ~30s).
  xfer = CreateObject("roUrlTransfer")
  port = CreateObject("roMessagePort")
  xfer.SetPort(port)
  xfer.SetCertificatesFile("common:/certs/ca-bundle.crt")
  xfer.EnablePeerVerification(true)
  xfer.EnableHostVerification(true)
  xfer.AddHeader("Accept", "application/json")
  xfer.AddHeader("Authorization", authHeader())
  xfer.AddHeader("X-Emby-Authorization", authHeader())
  xfer.AddHeader("Content-Type", "application/json")
  q = Chr(34)
  body = "{" + q + "PlayableMediaTypes" + q + ":[" + q + "Video" + q + "]," + q + "SupportedCommands" + q + ":[]," + q + "SupportsMediaControl" + q + ":false," + q + "SupportsPersistentIdentifier" + q + ":true}"
  ok = xfer.SetUrl(base + "/Sessions/Capabilities/Full")
  if ok = true
    xfer.AsyncPostFromString(body)
  end if
  m.sessionXfer = xfer
  m.sessionPort = port
end sub

function probeReach() as object
  base = trimSlash(m.top.baseUrl)
  if base = "" then return { reachable: false, error: "baseUrl not set" }
  resp = httpRequestWait("GET", base + "/System/Info/Public", "", 8000)
  if resp.code = 200 then return { reachable: true }
  detail = "HTTP " + resp.code.toStr()
  if resp.reason <> invalid and resp.reason <> "" then detail = detail + ": " + resp.reason
  return { reachable: false, error: detail }
end function

function urlHost(url as string) as string
  ' crude host for error text
  u = url
  if Left(u, 7) = "http://" then u = Mid(u, 8)
  if Left(u, 8) = "https://" then u = Mid(u, 9)
  slash = Instr(1, u, "/")
  if slash > 0 then u = Left(u, slash - 1)
  return u
end function

function flockIndexCap() as integer
  return 313
end function

function flockFetchLimit() as integer
  return 5000
end function

function pruneToCap(src as object, cap as integer) as object
  out = []
  if src = invalid then return out
  for each it in src
    out.push(it)
  end for
  n = out.count()
  if n <= cap then return out
  for i = n - 1 to 1 step -1
    j = Rnd(i + 1) - 1
    tmp = out[i]
    out[i] = out[j]
    out[j] = tmp
  end for
  pruned = []
  i = 0
  while i < cap
    pruned.push(out[i])
    i = i + 1
  end while
  return pruned
end function

function takeFirst(src as object, cap as integer) as object
  out = []
  if src = invalid then return out
  i = 0
  for each it in src
    if i >= cap then exit for
    out.push(it)
    i = i + 1
  end for
  return out
end function

function sortModeValue() as string
  raw = m.top.sortMode
  if raw = invalid then raw = ""
  tl = LCase(raw.Trim())
  if tl = "alias" or tl = "generation" or tl = "duration" or tl = "license" or tl = "folder"
    return tl
  end if
  return "filename"
end function

function isAllDigits(raw as string) as boolean
  if raw = invalid or raw = "" then return false
  i = 1
  while i <= Len(raw)
    ch = Mid(raw, i, 1)
    if ch < "0" or ch > "9" then return false
    i = i + 1
  end while
  return true
end function

function filenameSortKey(it as object) as string
  name = ""
  if it <> invalid and it.filename <> invalid then name = LCase(it.filename.Trim())
  if name = "" or name = "untitled" then return "~"
  return name
end function

function aliasSortKey(it as object) as string
  alias = ""
  if it <> invalid and it.alias <> invalid then alias = LCase(it.alias.Trim())
  if alias <> "" then return alias
  return filenameSortKey(it)
end function

function licenseSortKey(it as object) as string
  lic = ""
  if it <> invalid and it.license <> invalid then lic = LCase(it.license.Trim())
  if lic = "" then return "~"
  return lic
end function

function generationRank(it as object) as integer
  tag = ""
  if it <> invalid and it.gridTag <> invalid then tag = it.gridTag
  if tag = "breed" then return 1
  if tag = "tuple" then return 2
  gen = ""
  if it <> invalid and it.generation <> invalid then gen = it.generation
  if isAllDigits(gen) then return 0
  return 3
end function

function flockSortBefore(a as object, b as object, mode as string) as boolean
  if mode = "alias"
    return aliasSortKey(a) < aliasSortKey(b)
  else if mode = "generation"
    ra = generationRank(a)
    rb = generationRank(b)
    if ra <> rb then return ra < rb
    if ra = 0
      gaRaw = "0"
      gbRaw = "0"
      if a.generation <> invalid then gaRaw = a.generation
      if b.generation <> invalid then gbRaw = b.generation
      ga = Val(gaRaw)
      gb = Val(gbRaw)
      if ga <> gb then return ga < gb
      sa = 0
      sb = 0
      saRaw = ""
      sbRaw = ""
      if a.sheepId <> invalid then saRaw = a.sheepId
      if b.sheepId <> invalid then sbRaw = b.sheepId
      if isAllDigits(saRaw) then sa = Val(saRaw)
      if isAllDigits(sbRaw) then sb = Val(sbRaw)
      if sa <> sb then return sa < sb
    end if
    return filenameSortKey(a) < filenameSortKey(b)
  else if mode = "duration"
    la = 0
    lb = 0
    if a <> invalid and a.length <> invalid then la = a.length
    if b <> invalid and b.length <> invalid then lb = b.length
    if la <> lb then return la < lb
    return filenameSortKey(a) < filenameSortKey(b)
  else if mode = "license"
    ka = licenseSortKey(a)
    kb = licenseSortKey(b)
    if ka <> kb then return ka < kb
    return filenameSortKey(a) < filenameSortKey(b)
  end if
  return filenameSortKey(a) < filenameSortKey(b)
end function

' Stable insertion sort. folder keeps the folder-walk order from fetchList.
function sortFlock(items as object, mode as string) as object
  if items = invalid then return []
  if mode = "folder" then return items
  out = []
  for each it in items
    out.push(it)
  end for
  n = out.count()
  i = 1
  while i < n
    held = out[i]
    j = i - 1
    while j >= 0
      if flockSortBefore(held, out[j], mode) <> true then exit while
      out[j + 1] = out[j]
      j = j - 1
    end while
    out[j + 1] = held
    i = i + 1
  end while
  return out
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

  fetchLimit = flockFetchLimit()
  libId = ""
  if m.top.libraryId <> invalid and m.top.libraryId <> "" then libId = m.top.libraryId

  fetched = fetchRawItems(base, libId, fetchLimit)
  if fetched.error <> invalid
    return { error: fetched.error, debugUrl: fetched.debugUrl }
  end if
  raw = fetched.items
  ' Always walk child folders when libraryId is set — empty-only fallback misses
  ' partial flat hits (lab: 1 of 6 sheep under by-generation/).
  if libId <> ""
    nested = fetchItemsViaChildFolders(base, libId, fetchLimit)
    raw = mergeItemsById(nested, raw, fetchLimit)
  end if
  ' Commercial filtering is client-side via isCommercialSafe() below.

  items = []
  ncCount = 0
  ncExcluded = 0
  filteredCount = 0
  for each it in raw
    isNc = hasNcLicense(it)
    if isNc then ncCount = ncCount + 1
    if m.top.commercialMode = true
      if isCommercialSafe(it)
        items.push(mapItem(it, base))
      else
        filteredCount = filteredCount + 1
        if isNc then ncExcluded = ncExcluded + 1
      end if
    else
      items.push(mapItem(it, base))
    end if
  end for
  mode = sortModeValue()
  items = sortFlock(items, mode)
  if mode = "folder"
    items = pruneToCap(items, flockIndexCap())
  else
    items = takeFirst(items, flockIndexCap())
  end if
  aliasCount = 0
  for each mapped in items
    if mapped.alias <> invalid and mapped.alias <> "" then aliasCount = aliasCount + 1
  end for
  return {
    items: items
    count: items.count()
    sourceCount: raw.count()
    filteredCount: filteredCount
    ncCount: ncCount
    ncExcluded: ncExcluded
    aliasCount: aliasCount
  }
end function

function hasNcLicense(it as object) as boolean
  if it.Tags = invalid then return false
  for each t in it.Tags
    tl = LCase(t)
    if tl = "cc-by-nc" or tl = "cc-by-nc-sa" or Instr(1, tl, "by-nc") > 0
      return true
    end if
  end for
  return false
end function

function hasSafeLicense(it as object) as boolean
  if it.Tags = invalid then return false
  for each t in it.Tags
    tl = LCase(t)
    if tl = "cc-by" or tl = "cc-by-sa" or tl = "cc0" or tl = "public-domain" or tl = "pd"
      return true
    end if
  end for
  return false
end function

function isCommercialSafe(it as object) as boolean
  ' NC always wins, regardless of Jellyfin tag order or an additional safe tag.
  if hasNcLicense(it) then return false
  return hasSafeLicense(it)
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
    else if tl = "cc-by-nc" or tl = "cc-by-nc-sa" or Instr(1, tl, "by-nc") > 0
      license = tl
    else if tl = "cc-by" or tl = "cc-by-sa"
      if license = "" then license = tl
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

  ' Overview lines: "License: cc-by-nc" / "Alias: frosty_swirles"
  ov = ""
  if it.Overview <> invalid then ov = it.Overview
  if license = "" then license = overviewKeyedValue(ov, "License:")
  alias = overviewKeyedValue(ov, "Alias:")

  return {
    generation: generation
    license: license
    pedigree: pedigree
    sheepId: sheepId
    alias: alias
  }
end function

function overviewKeyedValue(ov as string, key as string) as string
  if ov = invalid or ov = "" or key = invalid or key = "" then return ""
  li = Instr(1, ov, key)
  if li = 0 then li = Instr(1, LCase(ov), LCase(key))
  if li = 0 then return ""
  frag = Mid(ov, li + Len(key)).Trim()
  nl = Instr(1, frag, Chr(10))
  if nl > 0 then frag = Left(frag, nl - 1)
  frag = frag.Trim()
  if LCase(key) = "license:"
    sp = Instr(1, frag, " ")
    if sp > 0 then frag = Left(frag, sp - 1)
    return LCase(frag)
  end if
  return frag
end function

function titleModeValue() as string
  raw = m.top.titleMode
  if raw = invalid then raw = ""
  tl = LCase(raw.Trim())
  if tl = "alias" then return "alias"
  return "filename"
end function

function displayTitle(filename as string, alias as string) as string
  if titleModeValue() = "alias" and alias <> invalid and alias <> "" then return alias
  if filename <> invalid and filename <> "" then return filename
  if alias <> invalid and alias <> "" then return alias
  return "Untitled"
end function

' Poster tag: numbered gens stay "gen N". Mutations of every breed method
' share "breed". Tuple clips share "tuple". misc/test stay off the tile.
function posterGridTag(meta as object, filename as string, mediaPath as string) as string
  blob = ""
  if filename <> invalid then blob = filename
  if mediaPath <> invalid and mediaPath <> "" then blob = blob + " " + mediaPath
  low = LCase(blob)
  gen = ""
  if meta <> invalid and meta.generation <> invalid then gen = LCase(meta.generation)
  if Instr(1, low, ".tuple.") > 0 or Instr(1, low, "/tuple/") > 0 or Instr(1, low, "\tuple\") > 0 or gen = "tuple"
    return "tuple"
  end if
  if Instr(1, low, ".pedigree.") > 0 or Instr(1, low, "/pedigree/") > 0 or Instr(1, low, "\pedigree\") > 0 or gen = "pedigree"
    return "breed"
  end if
  sheep = ""
  if meta <> invalid and meta.sheepId <> invalid then sheep = LCase(meta.sheepId)
  ped = ""
  if meta <> invalid and meta.pedigree <> invalid then ped = LCase(meta.pedigree)
  if sheep = "mutate" or sheep = "cross" or sheep = "blend" or sheep = "interpolate" then return "breed"
  if Instr(1, ped, "mutate") > 0 or Instr(1, ped, "cross") > 0 or Instr(1, ped, "blend") > 0 or Instr(1, ped, "interpolate") > 0
    return "breed"
  end if
  if isAllDigits(gen) then return "gen " + meta.generation
  return ""
end function

function buildMetaLine(durationLabel as string, meta as object, filename as string, mediaPath as string) as string
  bits = []
  if durationLabel <> "" then bits.push(durationLabel)
  tag = posterGridTag(meta, filename, mediaPath)
  if tag <> "" then bits.push(tag)
  if meta.license <> invalid and meta.license <> ""
    bits.push(meta.license)
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
  filename = "Untitled"
  if it.Name <> invalid and it.Name <> "" then filename = it.Name
  meta = extractMeta(it)
  alias = ""
  if meta.alias <> invalid then alias = meta.alias
  title = displayTitle(filename, alias)
  mediaPath = ""
  if it.Path <> invalid then mediaPath = it.Path
  gridTag = posterGridTag(meta, filename, mediaPath)
  metaLine = buildMetaLine(durationLabel, meta, filename, mediaPath)
  hls = hlsStreamUrl(base, it.Id)
  mp4 = mp4StreamUrl(base, it.Id)
  ' url stays HLS for deep-link/list compatibility; PlayerScreen picks via streamMode.
  return {
    id: it.Id
    title: title
    filename: filename
    alias: alias
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
    gridTag: gridTag
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
  if m.top.commercialMode = true and isCommercialSafe(data) <> true
    return { error: "item excluded by commercialMode", items: [], count: 0 }
  end if
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
