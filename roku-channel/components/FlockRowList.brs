function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  ' RowList often swallows options before Scene.onKeyEvent sees it
  if key = "options" or key = "info" or key = "lit_asterisk"
    m.top.requestSettings = true
    return true
  end if
  return false
end function
