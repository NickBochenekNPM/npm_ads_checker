// Google Apps Script — this file does NOT declare onOpen(). It lives in the
// same Apps Script project as other sheet tools (e.g. AdGrantAnalyzer.gs),
// and the shared menu.gs file owns the single onOpen() for the whole
// project, wiring 'Run Ads Check' to runAdsCheck() below.
//
// To let people set up a brand-new workspace (a new "<name> - Ads Checker
// Input/Output" tab pair), add: .addItem('Set up new workspace (Ads Checker)', 'initWorkspace')

var SERVICE_URL = 'https://ads-checker-127286750848.us-central1.run.app';
var INPUT_SUFFIX = ' - Ads Checker Input';
var OUTPUT_SUFFIX = ' - Ads Checker Output';

// Derives the workspace name from whichever tab is active when the menu is
// clicked, e.g. "Kristen - Ads Checker Input" -> "Kristen". Returns null if
// the active tab isn't one of the Ads Checker tabs.
function getActiveWorkspace() {
  var name = SpreadsheetApp.getActiveSheet().getName();
  if (name.endsWith(INPUT_SUFFIX)) return name.slice(0, -INPUT_SUFFIX.length);
  if (name.endsWith(OUTPUT_SUFFIX)) return name.slice(0, -OUTPUT_SUFFIX.length);
  return null;
}

function initWorkspace() {
  var ui = SpreadsheetApp.getUi();
  var response = ui.prompt(
    'Ads Checker — Set up new workspace',
    'What name should the new workspace use? (e.g. "Dana" creates the\n"Dana - Ads Checker Input" / "Dana - Ads Checker Output" tabs)',
    ui.ButtonSet.OK_CANCEL
  );
  if (response.getSelectedButton() !== ui.Button.OK) return;
  var user = response.getResponseText().trim();
  if (!user) return;

  try {
    var httpResponse = UrlFetchApp.fetch(
      SERVICE_URL + '/init?user=' + encodeURIComponent(user),
      { method: 'get', muteHttpExceptions: true }
    );
    var data = JSON.parse(httpResponse.getContentText());
    if (data.status === 'ok') {
      ui.alert('Ads Checker', data.message, ui.ButtonSet.OK);
    } else {
      ui.alert('Ads Checker — Error', data.message || 'Unknown error', ui.ButtonSet.OK);
    }
  } catch (e) {
    ui.alert('Ads Checker — Error', e.message, ui.ButtonSet.OK);
  }
}

function runAdsCheck() {
  var ui = SpreadsheetApp.getUi();
  var user = getActiveWorkspace();
  if (!user) {
    ui.alert(
      'Ads Checker',
      'Select your "<name> - Ads Checker Input" or "...Output" tab first, then run this again.',
      ui.ButtonSet.OK
    );
    return;
  }

  try {
    var response = UrlFetchApp.fetch(
      SERVICE_URL + '/run?user=' + encodeURIComponent(user),
      { method: 'get', muteHttpExceptions: true }
    );
    var data = JSON.parse(response.getContentText());
    if (data.status === 'ok') {
      ui.alert(
        'Ads Checker',
        'Enqueued ' + data.enqueued + ' domain(s).\nResults will appear in "' + user + ' - Ads Checker Output" as they complete.',
        ui.ButtonSet.OK
      );
    } else {
      ui.alert('Ads Checker — Error', data.message || 'Unknown error', ui.ButtonSet.OK);
    }
  } catch (e) {
    ui.alert('Ads Checker — Error', e.message, ui.ButtonSet.OK);
  }
}
