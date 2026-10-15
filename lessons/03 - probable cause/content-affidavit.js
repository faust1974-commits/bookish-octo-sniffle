// The worksheet. Five parts, one per standard, in the order the reasoning has
// to happen: review the report, climb the ladder, find the law, prove each
// element, then write the oath — and then say what it does NOT prove.
module.exports = {
  title: 'Probable Cause',
  subtitle: 'Lincoln Community Center · report review, statute, affidavit',

  brief: 'Everything you have written so far recorded what happened. This is different. An affidavit is a sworn document — you sign it under oath, and a judge reads it to decide whether somebody loses their liberty. You do not get to be approximately right.',

  /* ---------------------------------------------------- levels of proof */
  ladderHeading: 'The levels of proof',
  ladderPrompt: 'Every action a law enforcement officer takes requires a level of proof, and they are not interchangeable. Keep this in front of you all period.',
  ladderCols: ['Level', 'What it means', 'What it lets you do'],
  ladderWidths: [2300, 4100, 2960],
  ladder: [
    ['Hunch', 'A feeling. Nothing you can point to.', 'Nothing. You may not act on it.'],
    ['Reasonable suspicion', 'Specific facts you can put into words that suggest a crime.', 'Briefly stop and detain someone to investigate.'],
    ['Probable cause', 'Facts that would lead a reasonable person to believe a crime was committed and that this person committed it.', 'Arrest. Apply for a search warrant. Charge someone.'],
    ['Preponderance of the evidence', 'More likely than not. The civil standard.', 'Win a civil case. Not a criminal one.'],
    ['Beyond a reasonable doubt', 'The highest standard there is.', 'Convict at trial. This is the jury’s job, never yours.'],
  ],
  ladderNote: 'You are writing at the <strong>probable cause</strong> level today. Not reasonable suspicion, and not beyond a reasonable doubt. One rung, and you have to hit it exactly.',

  /* ---------------------------------------------------------- A. review */
  partA: {
    label: 'PART A',
    heading: 'Review the report you already wrote',
    prompt: 'Open your incident report and your supplemental. Read your own narrative back. An officer reviews a report before it leaves their hands, every time — because once it is filed, it is evidence, and so is every mistake in it.',
    checkIntro: 'Put an X in the box only if it is actually true of your report.',
    check: [
      'Every sentence can be traced to the dispatch entry, Delgado, or Vance.',
      'I wrote in the first person and in the past tense throughout.',
      'I attributed every statement to the person who made it.',
      'There is no conclusion in my report that I did not personally see or get told.',
      'I did not use the word burglary as though it were established fact.',
      'Anything I could not establish is recorded as unresolved, not guessed at.',
      'Someone who has never heard of this case could follow it start to finish.',
    ],
    fixLabel: 'The one thing I would change about my report now',
    fixPrompt: 'Be specific. Not “write neater” — name the sentence and say what was wrong with it.',
    whereLabel: 'Before the pawn record arrived, where was this case on the ladder?',
    wherePrompt: 'Against a named person. Pick a level and say why in one sentence.',
  },

  /* --------------------------------------------------------- B. statute */
  partB: {
    label: 'PART B',
    heading: 'Find the law',
    prompt: 'A report describes what happened. A charge has to name a statute. Nobody is going to hand you the number — locating it is the job, and you will do it the same way for the rest of your career.',
    howTo: [
      'Go to <strong>flsenate.gov</strong> and open Laws, then Florida Statutes.',
      'Find <strong>Chapter 812 — Theft, Robbery, and Related Crimes</strong>.',
      'Inside Chapter 812, find the section that defines theft. Read subsection (1) for what theft <em>is</em>, then subsection (2) for how the degree changes with the value of the property.',
      'Nine laptops at about $520 each. Work out the total, then find the tier that total falls into.',
    ],
    fields: [
      { id: 'cite', label: 'Statute citation', prompt: 'Chapter and section, the way a court would write it.', w: 'half' },
      { id: 'offense', label: 'Name of the offence', prompt: 'Exactly as the statute names it.', w: 'half' },
      { id: 'total', label: 'Total value of the property taken', prompt: 'Show your arithmetic, and say whose figure the unit price is.', w: 'half' },
      { id: 'degree', label: 'Degree of the offence', prompt: 'Which tier does your total fall into, and what does the statute call it?', w: 'half' },
      { id: 'tier', label: 'Quote the exact words of the tier you landed on', prompt: 'Copy the statute’s own language. Do not paraphrase a law you are about to swear to.', w: 'full', rows: 3 },
    ],
  },

  /* -------------------------------------------------------- C. elements */
  partC: {
    label: 'PART C',
    heading: 'Prove it element by element',
    prompt: 'A statute is a list of parts. Every single part has to be matched to a fact, and every fact has to come from somewhere in your file. If you cannot fill a row, you do not have probable cause — you have a theory.',
    note: 'Read your statute again and list each element it requires. Then match it. <strong>Source</strong> means name the document and the person: “Vance statement”, “pawn record”, “my own observation”.',
    cols: ['Element the statute requires', 'The fact that satisfies it', 'Source of that fact'],
    widths: [3100, 3300, 2960],
    rows: 5,
  },

  /* ------------------------------------------------------- D. affidavit */
  partD: {
    label: 'PART D',
    heading: 'The affidavit',
    prompt: 'Short, specific, and sworn. A judge reads this and nothing else. Do not retell your whole narrative — state the facts that establish each element, name your sources, and stop.',
    blocks: [
      {
        name: 'Defendant',
        fields: [
          { id: 'def', label: 'Name, date of birth, and address', prompt: 'As recorded on the pawn record. Do not improve on it.', w: 'full', rows: 2 },
          { id: 'ident', label: 'How this person was identified', prompt: 'What specifically ties this name to these items? Be exact — this is the sentence a defence attorney attacks first.', w: 'full', rows: 3 },
        ],
      },
      {
        name: 'The charge',
        fields: [
          { id: 'charge', label: 'Offence and statute citation', prompt: 'From Part B.', w: 'half' },
          { id: 'cdegree', label: 'Degree', prompt: 'From Part B.', w: 'half' },
          { id: 'when', label: 'When the offence occurred', prompt: 'Can you give a time, or only a window? Say which, and whose account it rests on.', w: 'half' },
          { id: 'where', label: 'Where the offence occurred', prompt: 'Address and the specific part of the building.', w: 'half' },
        ],
      },
      {
        name: 'Sworn statement of probable cause',
        fields: [
          { id: 'sworn', label: 'Sworn statement of probable cause', prompt: 'First person, past tense, facts and sources only. Walk the judge from the report to the asset tags to the pawn record. Eight to twelve sentences is plenty.', w: 'full', rows: 14 },
        ],
      },
    ],
    oathHeading: 'Oath',
    oathText: 'Under penalty of perjury, I declare that I have read the foregoing and that the facts stated in it are true to the best of my knowledge and belief.',
    oathFields: 'Affiant signature: ____________________________________     Printed name: ____________________________________\n\nDate: ______________     Sworn to and subscribed before me this ______ day of ______________, 20____\n\nNotary or authorised officer: ____________________________________',
  },

  /* ----------------------------------------------------------- E. limits */
  partE: {
    label: 'PART E',
    heading: 'What this affidavit does not establish',
    prompt: 'This is the part that separates an officer from somebody guessing. You have probable cause for one thing. Say plainly what you still cannot prove — in writing, in the file, where a prosecutor will see it.',
    cols: ['What I cannot prove', 'What it would take to prove it'],
    widths: [4680, 4680],
    rows: 4,
    bigQuestionLabel: 'The burglary question',
    bigQuestionPrompt: 'The call came in as a burglary. Burglary requires proof that somebody entered the building unlawfully. Do you have probable cause to charge burglary? Answer yes or no and defend it in two or three sentences.',
  },
};
