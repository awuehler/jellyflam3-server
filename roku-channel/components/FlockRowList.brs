function init()
  m.wrapTimer = m.top.findNode("wrapTimer")
  m.wrapTimer.observeField("fire", "onWrapFire")
  m.wrapPending = false
end function

function onKeyEvent(key as string, press as boolean) as boolean
  if not press then return false
  ' RowList often swallows options before Scene.onKeyEvent sees it
  if key = "options" or key = "info" or key = "lit_asterisk"
    m.top.requestSettings = true
    return true
  end if
  ' A full row or a tall list wraps in the RowList itself. Only a short
  ' row or a short list needs a deferred jump, and that jump must not run
  ' inside this handler.
  if wrapGridKey(key) then return true
  return false
end function

' Horizontal wrap stays on the current row. Vertical wrap keeps the column and
' clamps it when the destination row is shorter (the last row of a partial flock).
' One tile or one row does not wrap, so a small flock stays put at that edge.
function wrapGridKey(key as string) as boolean
  if m.top.content = invalid then return false
  focused = m.top.rowItemFocused
  if focused = invalid or focused.count() < 2 then return false
  row = focused[0]
  col = focused[1]
  rowCount = m.top.content.getChildCount()
  if rowCount <= 0 or row < 0 or row >= rowCount then return false
  rowNode = m.top.content.getChild(row)
  if rowNode = invalid then return false
  colCount = rowNode.getChildCount()
  if colCount <= 0 then return false

  if key = "right" or key = "left"
    if colCount <= 1 then return false
    ' Five tiles fill the 1760px row, so fixedFocusWrap slides that row.
    if colCount >= 5 then return false
    if key = "right" and col < colCount - 1 then return false
    if key = "left" and col > 0 then return false
    dest = 0
    if key = "left" then dest = colCount - 1
    scheduleWrap(row, dest)
    return true
  end if

  if key = "down" or key = "up"
    if rowCount <= 1 then return false
    ' Taller than the screen: vertFocusAnimationStyle fixedFocusWrap slides.
    if rowCount > 3 then return false
    if key = "down" and row < rowCount - 1 then return false
    if key = "up" and row > 0 then return false
    destRow = 0
    if key = "up" then destRow = rowCount - 1
    scheduleWrap(destRow, clampedColumn(destRow, col))
    return true
  end if
  return false
end function

sub scheduleWrap(row as integer, col as integer)
  m.wrapRow = row
  m.wrapCol = col
  m.wrapPending = true
  m.wrapTimer.control = "stop"
  m.wrapTimer.control = "start"
end sub

' jumpToItem is a write-only row index, not a function. jumpToRowItem is the
' [row, col] field. Set it after onKeyEvent returns so the render thread is
' not re-entered while the list is still handling the key.
sub onWrapFire()
  if not m.wrapPending then return
  m.wrapPending = false
  m.top.jumpToRowItem = [m.wrapRow, m.wrapCol]
end sub

function clampedColumn(rowIndex as integer, column as integer) as integer
  if m.top.content = invalid then return 0
  rowNode = m.top.content.getChild(rowIndex)
  if rowNode = invalid then return 0
  count = rowNode.getChildCount()
  if count <= 0 then return 0
  if column < 0 then return 0
  if column >= count then return count - 1
  return column
end function
