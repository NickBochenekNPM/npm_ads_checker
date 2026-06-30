// Google Apps Script — paste this into your Sheet's script editor.
// Extensions > Apps Script > paste > Save > reload the Sheet.

var SERVICE_URL = 'https://ads-checker-127286750848.us-central1.run.app';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('Ads Checker')
    .addItem('Run check', 'runAdsCheck')
    .addToUi();
}

function runAdsCheck() {
  var ui = SpreadsheetApp.getUi();
  try {
    var response = UrlFetchApp.fetch(SERVICE_URL + '/run', {
      method: 'get',
      muteHttpExceptions: true,
    });
    var data = JSON.parse(response.getContentText());
    if (data.status === 'ok') {
      ui.alert(
        'Ads Checker',
        'Enqueued ' + data.enqueued + ' domain(s).\nResults will appear in the Output tab as they complete.',
        ui.ButtonSet.OK
      );
    } else {
      ui.alert('Ads Checker — Error', data.message || 'Unknown error', ui.ButtonSet.OK);
    }
  } catch (e) {
    ui.alert('Ads Checker — Error', e.message, ui.ButtonSet.OK);
  }
}
