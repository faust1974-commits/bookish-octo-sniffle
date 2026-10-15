// Paste-ready Canvas build for the two-day report writing unit.
module.exports = {
  blurb: 'Three assignments across two 90-minute blocks. Build all three before Day 1, but assignment 3 stays hidden until minute 26 of Day 2 — the whole lesson depends on students not seeing the second witness until their questions are submitted.',

  assignments: [
    {
      label: '1',
      title: 'Incident Report — Lincoln Community Center',
      files: ['1 - Case File - Lincoln Community Center.docx', '2 - Incident Report Form - Lincoln Community Center.docx'],
      points: '40',
      submission: 'Online · file upload (they edit file 2 and submit it)',
      publish: 'Published before Day 1',
      hidden: false,
      description: [
        'You are the officer who took this call at 0107 hours. Everything you know is in the Case File: one dispatch entry and one witness statement. There is nothing else, and no more is coming.',
        'Fill in the Incident Report using only what is in the Case File.',
        'Two rules. First, if the Case File does not say it, you do not know it. Second, if you cannot fill in a field, leave it blank — do not guess, do not estimate, and do not write “unknown” unless you mean it. Blank is a real answer.',
        'Page 2 is the part that counts. Every blank you left is a question somebody has to answer before this case goes anywhere. List them: what you could not establish, who would know it, and how you would get it.',
        'Submit the report form when you are finished. Keep your copy — you will need it again.',
      ],
    },
    {
      label: '2A',
      title: 'Interview Preparation',
      files: ['3 - Interview Preparation.docx'],
      points: '20',
      submission: 'Online · file upload',
      publish: 'Published before Day 2',
      hidden: false,
      description: [
        'You get one interview to close the gaps in your report: Marisa Vance, the operations supervisor. One interview, no second chance.',
        'Work down your gap list from page 2 of your incident report. For every hole, write the question you would actually ask her — written out in full, the way you would say it out loud.',
        'Read the five rules at the top of the sheet first. They are the difference between a question that returns evidence and one that returns nothing.',
        'You will not receive her statement until this is submitted. You only get answers to the questions you actually ask.',
      ],
    },
    {
      label: '2B',
      title: 'Witness Statement and Supplemental Report',
      files: ['4 - Witness Statement - Marisa Vance.docx', '5 - Supplemental Report.docx'],
      points: '40',
      submission: 'Online · file upload (they edit file 5 and submit it)',
      publish: 'LEAVE UNPUBLISHED until minute 26 of Day 2',
      hidden: true,
      description: [
        'This is everything Marisa Vance told you. There is no third witness coming.',
        'Read her statement against your question sheet. Some of what you asked is answered here. Some of it is not — and that is also information.',
        'Then complete the Supplemental Report. A supplement adds to your original report; it does not repeat it and it does not replace it. New information only.',
        'Every line you write gets a name on it. Not “the door was unlocked” but “Vance stated the door is on a timer.” Every fact in a report has a source, and the source has a name.',
        'Delgado and Vance do not agree about the back door. Neither of them lied to you. Lay both accounts out in the Conflicting Information block, then write the one sentence you would actually put in the report. You do not get to decide who is right.',
        'Submit the Supplemental Report when you are finished.',
      ],
    },
  ],

  notes: [
    '<strong>File 6, Final Narrative and Self-Check, is not part of the two-day run.</strong> Keep it for absences and make-up work, or as an extension for students who finish early.',
    'Test one student-side upload yourself before Day 1: open file 2 in Word for the web and type into a table cell. The cells are set to grow rather than clip, but verify it against your own Office 365 and Canvas setup.',
    'Open board copies from your OneDrive, not from the Canvas preview — the preview is read-only and you will want to annotate over Delgado’s and Vance’s statements.',
  ],
};
