// Day 2 — the follow-up interview. Single source of truth for all three
// student files. Nothing here is improvised in the room: the supervisor is a
// document, released after the questions are submitted.
module.exports = {
  subtitle: 'Lincoln Community Center · overnight burglary',

  /* ---------------------------------------------- 3. interview preparation */
  prep: {
    title: 'Interview Preparation',
    brief: 'On Tuesday you listed what you could not establish. Today you get one interview to close those gaps — the operations supervisor, Marisa Vance. You only get the answers to the questions you actually ask, so write them before you ask them. Hand this in first. You will not receive her statement until you do.',

    rules: [
      '<strong>Open, not closed.</strong> <em>Was the door forced open?</em> gets you a yes or a no. <strong>Describe the door</strong> gets you a paragraph.',
      '<strong>One fact per question.</strong> If you ask two things at once you will only get an answer to one of them, and you will not know which.',
      '<strong>Never put the answer in the question.</strong> <em>You locked the equipment room, right?</em> tells her what you want to hear. <strong>Who locks the equipment room, and when?</strong> does not.',
      '<strong>Ask for the thing, not the opinion.</strong> <em>Do you think someone stole them?</em> is worthless in a report. <strong>How many laptops were in that room, and how do you know?</strong> is evidence.',
      '<strong>Ask how she knows.</strong> Every fact in your report needs a source. If she cannot say how she knows it, write that down too.',
    ],

    exampleHeading: 'Worked example',
    exampleGap: 'Gap from Tuesday: I could not establish how many laptops were taken.',
    exampleBad: 'Were there about ten laptops in there?',
    exampleBadWhy: 'Closed, and you supplied the number. She can agree with you and you have learned nothing you did not invent.',
    exampleGood: 'How many laptops were in the equipment room, and when did you last count them?',
    exampleGoodWhy: 'Open, one fact, no answer supplied, and it asks how she knows.',

    gridHeading: 'Your questions',
    gridPrompt: 'Work down your gap list from Tuesday. The questions you write here are the only ones that get answered.',
    gridCols: ['Gap I am trying to close', 'My question, written out in full'],
    gridRows: 8,

    rayHeading: 'If I could go back to Ray Delgado',
    rayPrompt: 'Three questions you should have asked the night custodian while you had him in front of you. This is how officers learn.',
    rayRows: 3,
  },

  /* --------------------------------------------- 4. the supervisor statement */
  vance: {
    title: 'Witness Statement',
    who: 'Marisa Vance — Operations Supervisor, Lincoln Community Center',
    note: 'Taken by you by telephone at 0214 hours, then in person at the center at 0640 hours. Written down as she said it.',

    admin: [
      ['INTERVIEWED', '0214 hours by telephone; 0640 hours in person'],
      ['NAME', 'Marisa Vance'],
      ['ROLE', 'Operations Supervisor — 4 years'],
      ['RELATIONSHIP', 'Ray Delgado’s direct supervisor'],
      ['CONTACT', 'Provided mobile number and work e-mail'],
    ],

    statement: [
      'Ray called me at ten minutes to one. I know that because it woke me up and I looked at my phone. I told him to call the police and not to touch anything, and then I got dressed and drove over.',
      'There were nine laptops in that room. I know because I counted them Friday afternoon when I locked up — that was about twenty to six. They are Dell, and they are asset tagged, CC-0041 through CC-0049. They cost us about five hundred and twenty dollars each when we bought them in February.',
      'Three people have a key to the equipment room. Me, the facility director, and there is one on the master ring in the office safe. Ray does not have one. He is not supposed to have one.',
      'The back door is on a timer. It locks itself at nine. I will be honest with you, that door does not always catch — I have put in two work orders on it since the spring and nobody has come out. So when Ray says it should have been locked, he is right, it should have been. Whether it was, I could not tell you.',
      'There is a camera over the back door. It has not worked since the summer. I put in a work order in July. Nobody came out for that one either.',
      'One more thing, and I am not saying this man did anything. We had a part-time rec aide over the summer, Dontae Rivers. His last day was the fifteenth of August. He never turned his key in. I sent him two e-mails about it. That was a building key, not the equipment room, but I am telling you because you asked who has keys.',
      'I have not been in the equipment room yet. The officer told me not to go in. So I cannot tell you if anything else is gone until I can get in there and look at my inventory sheet.',
    ],

    /* Printed on the statement so students can see what an interview does NOT
       produce. The point of the lesson is that this list is not a failure. */
    couldNotAnswerHeading: 'What she could not tell you',
    couldNotAnswer: [
      'Who entered the building, or how.',
      'What time the entry happened.',
      'Whether the back door was actually unlocked that night.',
      'Whether anything other than the laptops is missing.',
    ],
  },

  /* ------------------------------------------------- 5. supplemental report */
  supp: {
    title: 'Supplemental Report',
    brief: 'A supplemental report adds to the original. It does not replace it and it does not repeat it. Put only what is new here, and say who told you each thing. The same six rules apply: first person, past tense, facts and not conclusions, plain English.',

    blocks: [
      {
        n: 1, name: 'Administrative',
        fields: [
          { id: 'case', label: 'Case number', prompt: 'Same case number as your original report.', w: 'half' },
          { id: 'suppno', label: 'Supplement number', prompt: 'This is the first one. Number it.', w: 'half' },
          { id: 'date', label: 'Date and time of this supplement', prompt: 'When you wrote this, not when the incident happened.', w: 'half' },
          { id: 'officer', label: 'Reporting officer', prompt: 'You.', w: 'half' },
        ],
      },
      {
        n: 2, name: 'Person interviewed',
        fields: [
          { id: 'person', label: 'Name, role, and how you reached them', prompt: 'Full identification. A reader in two years has to be able to find this person again.', w: 'full', rows: 3 },
          { id: 'when', label: 'When and where the interview took place', prompt: 'Both contacts. Be exact — this is the part defence attorneys read first.', w: 'full', rows: 2 },
        ],
      },
      {
        n: 3, name: 'New information',
        fields: [
          { id: 'property', label: 'Property — what you can now establish', prompt: 'Quantity, make, asset tags, value, and <strong>how she knows</strong>. This is the block that was empty on Tuesday.', w: 'full', rows: 5 },
          { id: 'access', label: 'Access and keys', prompt: 'Who can get into that room, and who holds a key to the building. Attribute it.', w: 'full', rows: 4 },
          { id: 'timeline', label: 'Timeline — what you can now fix in time', prompt: 'You now have two times you did not have Tuesday. Which ones, and whose account are they from?', w: 'full', rows: 3 },
          { id: 'scene', label: 'Scene and surveillance', prompt: 'What she told you about the back door and the camera. Write what she said, not what it means.', w: 'full', rows: 4 },
        ],
      },
    ],

    conflictHeading: 'Conflicting information',
    conflictPrompt: 'Delgado and Vance do not agree about the back door. Neither of them is lying — they each know part of it. Lay both accounts out, then write the one sentence you would actually put in the report. You do not get to decide who is right. You attribute both and you move on.',
    conflictCols: ['What Delgado stated', 'What Vance stated'],
    conflictResolve: 'The sentence I would write in the report',

    leadsHeading: 'Leads for follow-up',
    leadsPrompt: 'Something a person has to go do next. A name is not a lead and it is not a suspect — the lead is the <strong>action</strong>. Watch yourself here: write what you would check, not what you think happened.',
    leadsCols: ['The lead', 'What I would do about it', 'Why it matters'],
    leadsRows: 5,

    openHeading: 'Still unresolved',
    openPrompt: 'What is still missing after the interview. An officer who knows what is missing is doing the job — that was true Tuesday and it is still true.',
    openRows: 4,
    openCols: ['What I still cannot establish', 'Who or what would answer it'],
  },
};
