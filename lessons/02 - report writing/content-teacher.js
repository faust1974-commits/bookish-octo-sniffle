// The run sheet. Written so it can be followed by someone who has not
// pre-read the case: every minute says what to do, and the lines you can read
// out loud are given in full.
module.exports = {
  title: 'Run Sheet',
  subtitle: 'Report Writing · Day 1 and Day 2 · 90-minute blocks',

  standards: [
    ['DAY 1 — CJO 2', '13.01 who-what-when-where-why-how · 13.04 purposes of reports · 13.06 organising information · 13.07 mechanics'],
    ['DAY 1 — CJO 3', '18.01 purpose of reports in investigations'],
    ['DAY 1 — CJO 1', '07.01 follow directions'],
    ['DAY 2 — CJO 2', '13.02 demonstrate interviewing a person · 13.03 demonstrate accurate note taking'],
    ['DAY 2 — CJO 1', '07.11 interviewing techniques used with witnesses and victims'],
  ],

  bigIdea: 'Everything after the report — the arrest, the charge, the trial, the conviction — runs on the report. The officer is never in the room when it is read. Students are not learning to write; they are learning that a claim is only worth what supports it.',

  grading: [
    '<strong>Day 1: grade page 2 only.</strong> Three columns, eight rows, fifteen seconds a student. Do not grade the narrative on Day 1.',
    '<strong>Day 2: grade the exit ticket only.</strong> One sentence. You are looking for attribution, not a verdict.',
    '<strong>Full narrative grading waits for Lesson 3,</strong> when they finally have enough facts to write one.',
  ],

  days: [
    {
      label: 'DAY 1',
      heading: 'The format',
      files: ['1 — Case File (reference, also on the board)', '2 — Incident Report Form (they type in this one and submit it)'],
      goal: 'They learn the shape of a report, and they discover they cannot finish one. The gaps are the deliverable.',
      steps: [
        { t: '0–5', what: 'Settle. They open Canvas and both files.',
          say: 'A case is only as good as the report. Everything that happens after tonight — the arrest, the trial, the conviction — runs on this one document.' },
        { t: '5–12', what: 'Frame who reads a report: the next shift, a detective, a prosecutor, a defence attorney, a jury, two years later. The officer is never there to explain it.',
          say: 'You will never be in the room when your report is read. It has to work without you.' },
        { t: '12–25', what: 'Walk the five blocks on the board. Point at the form, do not lecture. Block 1 administrative, Block 2 persons, Block 3 property and evidence, Block 4 narrative, Block 5 status. Say what each block is for and move on.',
          say: 'Each block has one job. If information is in the wrong block, the person who needs it will not find it.' },
        { t: '25–35', what: 'Put the Case File on the board. A student reads all four of Ray Delgado’s paragraphs aloud, slowly. Then read it a second time. They will not catch what is missing the first time.',
          say: 'Listen for what he does not say.' },
        { t: '35–42', what: 'Model Block 1 together on the board. Spend the time on OFFENSE TYPE. The form asks whether burglary is supportable — burglary needs entry plus intent, and nobody saw either. Let them argue. Land somewhere defensible.',
          say: 'Can you prove entry? Can you prove intent? If you cannot, you do not get to write the word.' },
        { t: '42–72', what: 'Independent, on Chromebooks. Blocks 1 through 5, from the Case File only. Circulate. The only question you have to answer is “can I just put…” — and the answer is always no, leave it blank.',
          say: 'If the Case File does not say it, you do not know it.' },
        { t: '72–84', what: 'Page 2 — What I still need to find out. Three columns. This is the real assignment and the bridge to Thursday.',
          say: 'Every blank above is a question somebody has to answer. An officer who knows what is missing is doing the job.' },
        { t: '84–90', what: 'Cold-call four students for one gap each. Write them on the board. Leave them up.',
          say: 'Thursday you get to ask. But you only get answers to the questions you actually write down.' },
      ],
      watch: [
        '<strong>The narrative will be bad. That is the design.</strong> They do not have the facts to write one. Short and full of holes is correct output. A long, confident narrative means the student invented things — that is your teachable moment, not a failure.',
        '<strong>Do not rescue them.</strong> The frustration of a blank field is the lesson. Leave it blank.',
        '<strong>Someone will write that Ray did it.</strong> Ask them which sentence in the Case File supports that. There is not one.',
      ],
    },
    {
      label: 'DAY 2',
      heading: 'The interview',
      files: ['3 — Interview Preparation (they fill this in and submit it FIRST)', '4 — Witness Statement, Marisa Vance (you release this only after they submit)', '5 — Supplemental Report (they type in this one and submit it)'],
      goal: 'They learn that an interview returns only what you asked for, and that two honest witnesses can contradict each other.',
      steps: [
        { t: '0–8', what: 'Do-now: reopen Tuesday’s page 2. Circle your three worst gaps.',
          say: 'Those three holes are what today is for.' },
        { t: '8–18', what: 'Mini-lesson from the five rules on file 3. Do the board example: “Was the door forced open?” against “Describe the door.” Then the worked example on the sheet.',
          say: 'A closed question gets you a yes. A yes is not evidence. And if you put the number in the question, she can agree with you and you have learned nothing you did not make up yourself.' },
        { t: '18–32', what: 'They write their questions on file 3 and SUBMIT IT. This is a hard gate — nobody gets Vance’s statement until their questions are in.',
          say: 'You only get the answers to the questions you actually ask. That is not a classroom rule, that is the job.' },
        { t: '32–38', what: 'Release file 4. Put it on the board and read it aloud, same as Ray. Do not comment while you read.',
          say: null },
        { t: '38–55', what: 'They work the statement. Every line they take has to carry attribution — who said it, and how she knows it.',
          say: 'Vance stated. Not “it was.” Every fact in your report has a source and the source has a name.' },
        { t: '55–80', what: 'File 5, the Supplemental Report. New information only, attributed. Block 3 is the block that was empty on Tuesday — they can finally fill it.',
          say: 'A supplement adds. It does not repeat and it does not replace.' },
        { t: '80–90', what: 'THE CONTRADICTION. Put both lines side by side on the board — Delgado on the back door against Vance on the back door. Take the argument. Then land it.',
          say: 'Neither of them lied to you. They each know a piece of it. You do not get to decide who is right — you write both, you say who said which, and you let the investigation settle it. Exit ticket: write me that one sentence.' },
      ],
      watch: [
        '<strong>Hold the gate at minute 32.</strong> If you hand out Vance early the lesson collapses — the whole point is that weak questions return weak information.',
        '<strong>Dontae Rivers is not a suspect.</strong> Someone will write that he did it. Vance says the words “I am not saying this man did anything” and she says the key was a building key, not the equipment room key. The lead is <em>check whether that key was ever returned</em>, not <em>arrest him</em>.',
        '<strong>The two time discrepancies are deliberate.</strong> Ray says he called “around 1.” Vance says ten to one. Neither is wrong. Both get attributed. Students who flatten it into one time are losing information.',
        '<strong>The dead camera is the most realistic detail in the file.</strong> If someone is annoyed by it, that is the correct reaction and it is worth sixty seconds.',
      ],
    },
  ],

  answerKeyHeading: 'What the Vance statement is engineered to do',
  answerKey: [
    ['CLOSES', 'Laptop count (nine), make (Dell), asset tags (CC-0041 to CC-0049), unit value (about $520), who holds keys, when the room was last secured (Friday ~1740), when Ray called (1250).'],
    ['REFUSES', 'Who entered, how, exactly when, whether the back door was actually unlocked, whether anything else is gone. She has not been in the room yet.'],
    ['CONTRADICTS', 'The back door. Delgado: it should not be unlocked after 10. Vance: timer locks it at 9, but it does not always catch and she has filed two work orders. Both accounts are honest and partial.'],
    ['OPENS', 'An unreturned building key held by a former part-time employee — offered explicitly as a key-holder fact, not as an accusation.'],
  ],

  prepHeading: 'Before each class',
  prep: [
    'Day 1 — one Canvas assignment, files 1 and 2 attached. File 1 also open on the board.',
    'Day 2 — two Canvas assignments. First has file 3 only. Second has files 4 and 5, and stays unpublished until minute 32.',
    'Open the board copy from your own OneDrive, not from the Canvas preview — the preview is read-only and you will want to annotate.',
    'Test one student-side upload yourself before first period. Open the form in Word for the web and type in a table cell. The cells are set to grow, but verify it on your own setup.',
  ],
};
