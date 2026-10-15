// The evidence document that moves the case. Kept clean, like a real record —
// all the analysis happens on the worksheet, not on the exhibit.
module.exports = {
  title: 'Pawn Transaction Record',
  subtitle: 'Lincoln Community Center · follow-up evidence',

  howItCame: [
    'Three days after you took this report, you ran the asset tags you recorded in your supplemental report through the regional pawn transaction database. Pawnbrokers are required to record every transaction and report it to law enforcement, which is why this search is possible at all.',
    'Two of the nine asset tags came back. This is the record the pawnbroker filed. Nothing on it has been altered and nothing has been added.',
  ],

  transaction: [
    ['BUSINESS', 'Westside Pawn & Jewelry, 2210 Caldwell Avenue'],
    ['TRANSACTION NUMBER', 'WPJ-114-20886'],
    ['TYPE', 'Pawn — collateral loan'],
    ['DATE AND TIME', 'Saturday, 1042 hours'],
    ['CLERK', 'Filed by store manager, signature on file'],
  ],

  seller: [
    ['NAME GIVEN', 'Dontae M. Rivers'],
    ['DATE OF BIRTH', 'Recorded on form — age 23'],
    ['ADDRESS GIVEN', '1744 Perrine Road, Apt 12'],
    ['IDENTIFICATION', 'Florida driver licence, number recorded, photocopy on file'],
    ['THUMBPRINT', 'Taken at the counter and on file'],
  ],

  itemCols: ['Item', 'Description', 'Identifying marks', 'Amount advanced'],
  itemWidths: [1300, 3100, 2800, 2160],
  items: [
    ['1', 'Dell laptop computer, black', 'Asset tag CC-0043', '$60.00'],
    ['2', 'Dell laptop computer, black', 'Asset tag CC-0047', '$60.00'],
  ],
  itemTotal: ['', '', 'TOTAL ADVANCED', '$120.00'],

  noteHeading: 'Pawnbroker’s note on the record',
  note: 'Both units powered on at the counter. Asset tags were still attached to the underside of each unit and were not removed. Customer stated the items were his own property, as required on the form, and signed that statement.',

  footerHeading: 'What is in your file now',
  footer: [
    'Your original incident report and narrative.',
    'Ray Delgado’s statement.',
    'Marisa Vance’s statement, including the nine asset tags and the unreturned building key.',
    'Your supplemental report.',
    'This pawn transaction record.',
  ],
  footerNote: 'That is everything. Seven of the nine laptops are still unaccounted for.',
};
