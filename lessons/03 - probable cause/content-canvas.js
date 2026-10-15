// Paste-ready Canvas build. The description arrays are student-facing text.
module.exports = {
  blurb: 'Two assignments. Build them both before class, but leave the second one hidden — the lesson turns on the pawn record arriving at minute 32 and not before.',

  assignments: [
    {
      title: 'Probable Cause — Worksheet',
      files: ['2 - Probable Cause Worksheet.docx'],
      points: '40',
      submission: 'Online · file upload (they edit the .docx and submit it)',
      publish: 'Published before class',
      hidden: false,
      description: [
        'Open the worksheet and work through it in order. Do not skip ahead — Parts C, D and E need something you do not have yet.',
        'You will need your incident report and your supplemental report from last week. Have both open beside this.',
        'Part A: review your own report against the checklist. Be honest; nobody is marking the boxes. Then answer the two written questions underneath.',
        'Part B: find the law. Go to flsenate.gov, open Laws and then Florida Statutes, and find Chapter 812. Locate the section that defines theft. Copy the statute’s exact words for the tier you land on — do not put it in your own words.',
        'Part C: match every element the statute requires to a fact from your file, and name the document that fact came from.',
        'Part D: write the affidavit. Short and specific — eight to twelve sentences. You are not retelling your narrative.',
        'Part E: say plainly what this affidavit does not prove.',
        'Submit the worksheet when you are finished.',
      ],
    },
    {
      title: 'Probable Cause — Pawn Transaction Record',
      files: ['1 - Pawn Transaction Record.docx'],
      points: '0 — this is evidence, not an assignment',
      submission: 'No submission',
      publish: 'LEAVE UNPUBLISHED until minute 32',
      hidden: true,
      description: [
        'New evidence in the Lincoln Community Center case.',
        'Three days after you filed your report, the asset tags you recorded in your supplemental report were run through the regional pawn transaction database. Two of the nine came back.',
        'This is the record the pawnbroker filed. Read it carefully, then go back to Part C of your worksheet.',
      ],
    },
  ],

  notes: [
    '<strong>Check that Chromebooks can reach flsenate.gov before first period.</strong> If your filter blocks it, Part B has to come off the devices and go on the board instead.',
    'Remind students in the Canvas description of assignment 1 to bring last week’s two reports. Without them, Part A does not work.',
    'If you want a single gradebook column, make assignment 2 worth 0 points and ungraded — it exists only to deliver the document at the right moment.',
  ],
};
