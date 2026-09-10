' Flock artwork cycle: Jellyfin Primary + Backdrop stills (poster pipeline).
' Skip tuple folders/items. Never report playback (idle-gate safe).
' Always rotate — ignore shuffleFlock (VoD-only).

sub init()
  m.top.functionName = "runTask"
end sub

sub runTask()
  out = fetchArtworkUrls()
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
  return "MediaBrowser Client=""JellyFlam3-Screensaver"", Device=""Roku"", DeviceId=""jellyflam3-screensaver"", Version=""1.0.8"", Token=""" + m.top.apiKey + """"
end function

function commercialModeOn() as boolean
  v = m.top.commercialMode
  if v = invalid then return false
  tl = LCase(v.Trim())
  return (tl = "true" or tl = "1" or tl = "yes")
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

function isTuplePath(raw as dynamic) as boolean
  if raw = invalid then return false
  p = LCase(raw)
  if p = "tuple" then return true
  if Instr(1, p, "/tuple/") > 0 then return true
  if Instr(1, p, "\tuple\") > 0 then return true
  if Right(p, 6) = "/tuple" then return true
  if Instr(1, p, "electricsheep.tuple.") > 0 then return true
  return false
end function

function isTupleFolder(folder as object) as boolean
  if folder = invalid then return false
  if isTuplePath(folder.Name) then return true
  if isTuplePath(folder.Path) then return true
  return false
end function

function isTupleItem(it as object) as boolean
  if it = invalid then return false
  if isTuplePath(it.Name) then return true
  if isTuplePath(it.Path) then return true
  return false
end function

function httpGet(url as string) as object
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
  if xfer.SetUrl(url) <> true
    return { code: -1, body: "", reason: "SetUrl failed" }
  end if
  if xfer.AsyncGetToString() <> true
    return { code: -1, body: "", reason: "GET failed to start" }
  end if
  msg = wait(20000, port)
  if msg = invalid
    xfer.AsyncCancel()
    return { code: -1, body: "", reason: "timeout" }
  end if
  return { code: msg.GetResponseCode(), body: msg.GetString() }
end function

function fetchRawStillsItems(base as string, parentId as string, limit as integer) as object
  path = base + "/Users/" + m.top.userId + "/Items?IncludeItemTypes=Movie,Video&Recursive=true&ParentId=" + parentId + "&Fields=ImageTags,BackdropImageTags,Path,Tags,Name&Limit=" + limit.toStr() + "&SortBy=Random"
  resp = httpGet(path)
  if resp.code < 200 or resp.code >= 300
    return { error: "HTTP " + Str(resp.code).Trim(), items: [] }
  end if
  data = ParseJson(resp.body)
  if data = invalid or data.Items = invalid
    return { error: "bad JSON", items: [] }
  end if
  return { items: data.Items }
end function

function fetchStillsViaChildFolders(base as string, libraryId as string, limit as integer) as object
  fpath = base + "/Users/" + m.top.userId + "/Items?IncludeItemTypes=Folder&Recursive=false&ParentId=" + libraryId + "&Limit=50"
  resp = httpGet(fpath)
  if resp.code < 200 or resp.code >= 300 then return []
  data = ParseJson(resp.body)
  if data = invalid or data.Items = invalid then return []
  merged = []
  for each folder in data.Items
    if isTupleFolder(folder) then continue for
    if merged.count() >= limit then exit for
    fid = folder.Id
    if fid = invalid or fid = "" then continue for
    remain = limit - merged.count()
    batch = fetchRawStillsItems(base, fid, remain)
    if batch.error <> invalid then continue for
    batchItems = batch.items
    if batchItems = invalid then continue for
    for each it in batchItems
      if isTupleItem(it) then continue for
      merged.push(it)
      if merged.count() >= limit then exit for
    end for
  end for
  return merged
end function

function mergeStillsById(primary as object, extra as object, limit as integer) as object
  seen = {}
  out = []
  if primary <> invalid
    for each it in primary
      if out.count() >= limit then return out
      if it = invalid then continue for
      if isTupleItem(it) then continue for
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
      if isTupleItem(it) then continue for
      id = it.Id
      if id = invalid or id = "" then continue for
      if seen.DoesExist(id) then continue for
      seen.AddReplace(id, true)
      out.push(it)
    end for
  end if
  return out
end function

function artworkUrlsFromItems(base as string, raw as object) as object
  urls = []
  if raw = invalid then return urls
  commercial = commercialModeOn()
  for each it in raw
    if it = invalid then continue for
    if isTupleItem(it) then continue for
    if commercial and not isCommercialSafe(it) then continue for
    if it.Id = invalid or it.Id = "" then continue for
    id = it.Id
    if it.ImageTags <> invalid and it.ImageTags.Primary <> invalid and it.ImageTags.Primary <> ""
      urls.push(base + "/Items/" + id + "/Images/Primary?maxWidth=1920&api_key=" + m.top.apiKey)
    end if
    nBack = 0
    if it.BackdropImageTags <> invalid
      nBack = it.BackdropImageTags.count()
    end if
    i = 0
    while i < nBack
      urls.push(base + "/Items/" + id + "/Images/Backdrop/" + i.toStr() + "?maxWidth=1920&api_key=" + m.top.apiKey)
      i = i + 1
    end while
  end for
  return urls
end function

function shuffleCopy(src as object) as object
  bag = []
  if src = invalid then return bag
  for each u in src
    bag.push(u)
  end for
  n = bag.count()
  if n < 2 then return bag
  i = n - 1
  while i > 0
    j = Rnd(i + 1) - 1
    tmp = bag[i]
    bag[i] = bag[j]
    bag[j] = tmp
    i = i - 1
  end while
  return bag
end function

function fetchArtworkUrls() as object
  base = trimSlash(m.top.baseUrl)
  if base = "" then return { urls: [], error: "missing baseUrl" }
  libId = m.top.libraryId
  if libId = invalid or libId = "" then return { urls: [], error: "missing libraryId" }
  limit = 200
  fetched = fetchRawStillsItems(base, libId, limit)
  if fetched.error <> invalid
    return { urls: [], error: fetched.error }
  end if
  raw = fetched.items
  nested = fetchStillsViaChildFolders(base, libId, limit)
  raw = mergeStillsById(nested, raw, limit)
  urls = shuffleCopy(artworkUrlsFromItems(base, raw))
  return { urls: urls, count: urls.count() }
end function
