' Fetch flock Primary image URLs only. Never report playback (idle-gate safe).

sub init()
  m.top.functionName = "runTask"
end sub

sub runTask()
  out = fetchPrimaryUrls()
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
  ' Distinct Client so idle_gate ignore_client_patterns can match if a session appears.
  return "MediaBrowser Client=""JellyFlam3-Screensaver"", Device=""Roku"", DeviceId=""jellyflam3-screensaver"", Version=""1.0.6"", Token=""" + m.top.apiKey + """"
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
  path = base + "/Users/" + m.top.userId + "/Items?IncludeItemTypes=Movie,Video&Recursive=true&ParentId=" + parentId + "&Fields=ImageTags&Limit=" + limit.toStr() + "&SortBy=Random"
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

' Jellyfin 10.x: flat ParentId=library often returns a partial flock under by-generation/.
function fetchStillsViaChildFolders(base as string, libraryId as string, limit as integer) as object
  fpath = base + "/Users/" + m.top.userId + "/Items?IncludeItemTypes=Folder&Recursive=false&ParentId=" + libraryId + "&Limit=50"
  resp = httpGet(fpath)
  if resp.code < 200 or resp.code >= 300 then return []
  data = ParseJson(resp.body)
  if data = invalid or data.Items = invalid then return []
  merged = []
  for each folder in data.Items
    if merged.count() >= limit then exit for
    fid = folder.Id
    if fid = invalid or fid = "" then continue for
    remain = limit - merged.count()
    batch = fetchRawStillsItems(base, fid, remain)
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

function mergeStillsById(primary as object, extra as object, limit as integer) as object
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

function primaryUrlsFromItems(base as string, raw as object) as object
  urls = []
  if raw = invalid then return urls
  for each it in raw
    if it.Id <> invalid and it.ImageTags <> invalid and it.ImageTags.Primary <> invalid and it.ImageTags.Primary <> ""
      urls.push(base + "/Items/" + it.Id + "/Images/Primary?maxWidth=1920&api_key=" + m.top.apiKey)
    end if
  end for
  return urls
end function

function fetchPrimaryUrls() as object
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
  ' Always walk child folders — empty-only fallback misses partial flat hits.
  nested = fetchStillsViaChildFolders(base, libId, limit)
  raw = mergeStillsById(nested, raw, limit)
  urls = primaryUrlsFromItems(base, raw)
  return { urls: urls, count: urls.count() }
end function
