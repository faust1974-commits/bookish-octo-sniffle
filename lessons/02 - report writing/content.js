// Single source of truth for both the HTML worksheet and the Word version.
module.exports = {
  title: 'Incident Report — Practice 1',
  subtitle: 'Lincoln Community Center · overnight burglary',

  brief: 'You are the officer who took this call. Everything you know is on this page — the dispatch entry and one witness statement. Fill in the report below using only that information. Where you cannot answer a field, leave it blank and record it at the bottom under What I still need to find out. Do not invent anything. A report is only worth what it can support.',

  dispatch: [
    ['CALL RECEIVED', '0107 hours'],
    ['CALL TYPE', 'Burglary — just occurred'],
    ['LOCATION', 'Lincoln Community Center, 418 Mallory Street'],
    ['CALLER', 'Employee on scene, requesting an officer'],
    ['UNIT DISPATCHED', '0109 hours'],
    ['UNIT ON SCENE', '0116 hours'],
  ],

  witnessHeading: 'Witness statement — Ray Delgado, night custodian',
  witnessNote: 'Taken by you at the scene. Written down as he said it.',
  witness: [
    'I started my shift at 10. Everything looked normal on my first walk-through — that was maybe around 11, I’m not sure exactly.',
    'Later I went down the back hallway and the equipment room door was standing open. That door is always locked. The light was off. I didn’t go in, but I could see the shelf where the laptops are kept and it looked empty to me. I didn’t see anybody.',
    'I went back to the office and called my supervisor, and she said call the police. I think that was around 1 in the morning. I didn’t touch the door. There was something on the floor next to it, plastic or tape maybe, I didn’t look close.',
    'The back door to the parking lot was unlocked. It shouldn’t be after 10. I don’t know how many laptops were in there — my supervisor would know. There were no cars in the lot. I’ve worked here two years.',
  ],

  narrativeRules: [
    'Write as yourself: <strong>I responded</strong>, not <em>this officer responded</em>.',
    'Past tense, in the order things happened.',
    'Facts, not conclusions. <strong>I saw a piece of tape on the floor</strong>, not <em>someone taped the lock</em>.',
    'Say who told you what: <strong>Delgado stated that…</strong>',
    'Plain English. <strong>Got out of the car</strong>, not <em>exited the vehicle</em>.',
    'Complete enough that someone reading it in two years knows exactly what you found.',
  ],

  blocks: [
    {
      n: 1, name: 'Administrative',
      fields: [
        { id: 'case', label: 'Case number', prompt: 'Assigned by dispatch. Leave blank if you were not given one.', w: 'half' },
        { id: 'offense', label: 'Offense / incident type', prompt: 'What can you actually support from what you have? Burglary needs entry plus intent. Is there another, safer answer?', w: 'half' },
        { id: 'reported', label: 'Date and time reported', prompt: 'From the dispatch entry, not from the witness.', w: 'half' },
        { id: 'occurred', label: 'Date and time occurred', prompt: 'Can you give a time, or only a window? Say which.', w: 'half' },
        { id: 'location', label: 'Location', prompt: 'Street address, then the specific part of the building.', w: 'full' },
        { id: 'officer', label: 'Reporting officer and ID', prompt: 'You. Use your own name.', w: 'full' },
      ],
    },
    {
      n: 2, name: 'Persons',
      fields: [
        { id: 'complainant', label: 'Complainant / reporting person', prompt: 'Who called it in? Name, role, how long employed, how to reach him.', w: 'full', rows: 3 },
        { id: 'victim', label: 'Victim', prompt: 'Who suffered the loss? Is that the same person who called?', w: 'full', rows: 2 },
        { id: 'witnesses', label: 'Witnesses', prompt: 'Anyone who saw or heard something, and anyone you would need to speak to next. Name them even if you do not have their details.', w: 'full', rows: 3 },
        { id: 'suspect', label: 'Suspect', prompt: 'Only if someone described one. If nobody saw anyone, say so — do not leave a reader guessing.', w: 'full', rows: 2 },
      ],
    },
    {
      n: 3, name: 'Property and evidence',
      fields: [
        { id: 'property', label: 'Property taken or damaged', prompt: 'Item, description, quantity, serial number, value. Write only what you can support, and name who would know the rest.', w: 'full', rows: 4 },
        { id: 'evidence', label: 'Evidence observed or collected', prompt: 'Anything at the scene that could matter later. What did you see, where exactly, and what did you do about it?', w: 'full', rows: 3 },
      ],
    },
    {
      n: 4, name: 'Narrative',
      fields: [
        { id: 'narrative', label: 'Narrative', prompt: 'Start with how the call came to you. End with the last thing you did before leaving. Follow the six rules above.', w: 'full', rows: 14 },
      ],
    },
    {
      n: 5, name: 'Status',
      fields: [
        { id: 'status', label: 'Case status', prompt: 'Open, cleared by arrest, or referred. Which one is honest here?', w: 'half' },
        { id: 'followup', label: 'Follow-up assigned to', prompt: 'Who takes this next, and for what?', w: 'half' },
      ],
    },
  ],

  gapsHeading: 'What I still need to find out',
  gapsPrompt: 'Every blank above is a question somebody has to answer. List them. This section is worth as much as the narrative — an officer who knows what is missing is doing the job.',
  gapRows: 8,
  gapCols: ['What I could not establish', 'Who would know', 'How I would get it'],
};
