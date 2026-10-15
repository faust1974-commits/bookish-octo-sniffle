// File 6 — the closing deliverable. They finally have enough facts to write
// the narrative, so this is where the unit lands: narrative, the conflict they
// have to carry rather than resolve, and a self-check (13.09).
module.exports = {
  title: 'Final Narrative',
  subtitle: 'Lincoln Community Center · overnight burglary',

  brief: 'You now have everything you are ever going to get on this case: the dispatch entry, Ray Delgado, and Marisa Vance. No third witness is coming. Write the narrative. Every sentence has to come from one of those three places — if it does not, it does not go in.',

  rules: [
    'Write as yourself: <strong>I responded</strong>, not <em>this officer responded</em>.',
    'Past tense, in the order things happened.',
    'Facts, not conclusions. <strong>I saw a piece of tape on the floor</strong>, not <em>someone taped the lock</em>.',
    'Say who told you what: <strong>Delgado stated that…</strong>  <strong>Vance stated that…</strong>',
    'Plain English. <strong>Got out of the car</strong>, not <em>exited the vehicle</em>.',
    'Complete enough that someone reading it in two years knows exactly what you found.',
  ],

  /* Nobody should lose ten minutes to a blank box. */
  openerHeading: 'Your first two sentences',
  openerNote: 'Copy these, then keep going. The hard part is not starting, it is not inventing.',
  opener: [
    'At approximately 0107 hours I was dispatched to 418 Mallory Street, the Lincoln Community Center, for a burglary that had just occurred.',
    'I arrived on scene at 0116 hours and made contact with Ray Delgado, the night custodian, who stated that…',
  ],
  openerAfter: 'From there: what did Delgado show you, what did you see yourself, what did Vance add, and what was the last thing you did before you left?',

  narrativeLabel: 'Narrative',
  narrativePrompt: 'Start with how the call came to you. End with the last thing you did before leaving. Follow the six rules.',
  narrativeRows: 26,

  conflictHeading: 'The one thing that does not add up',
  conflictPrompt: 'Delgado and Vance do not agree about the back door. Neither of them lied to you — they each know part of it. Lay both accounts out, then write the single sentence you would actually put in the report. You do not get to decide who is right. You attribute both and you let the investigation settle it.',
  conflictCols: ['What Delgado stated', 'What Vance stated'],
  conflictResolveLabel: 'The one sentence I would put in the report',
  conflictResolvePrompt: 'Attribute both accounts. Do not pick a winner.',

  checkHeading: 'Self-check before you submit',
  checkPrompt: 'Every officer does this before the report leaves their hands. Read your own narrative against this list and be honest. Put an X in the box only if it is actually true.',
  check: [
    'Every sentence can be traced to the dispatch entry, Delgado, or Vance.',
    'I wrote in the first person and in the past tense throughout.',
    'I attributed every statement to the person who made it.',
    'There is no conclusion in here that I did not personally see or get told.',
    'I did not use the word burglary as though it were established fact.',
    'Someone who has never heard of this case could follow my narrative start to finish.',
    'Anything I could not establish is written down as unresolved, not guessed at.',
    'I read it through once, out loud or in my head, for spelling and grammar.',
  ],

  lastHeading: 'Last line',
  lastPrompt: 'One sentence: what is the single most important thing still unknown about this case?',
};
