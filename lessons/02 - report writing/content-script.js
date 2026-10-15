// The teacher's speaking parts, in order, with the cue for each.
// Lines starting with "[" are stage directions, not spoken.
// Written short and plain on purpose: these have to be sayable out loud by
// someone who has not pre-digested the case.
module.exports = {
  heading: 'Your Parts',
  blurb: 'Everything you say, in order. Each part is numbered, has its cue, and gives you the words. Bracketed lines are directions, not lines — do not read them out. Nothing here needs memorising; it needs saying.',

  parts: [
    /* ------------------------------------------------------------- DAY 1 */
    {
      day: 'DAY 1', n: 1, min: '0–12', name: 'The intro',
      cue: 'They are seated and have Canvas open. Nothing has been handed out yet.',
      lines: [
        'Everybody find two files in Canvas. Case File, and Incident Report.',
        'Here is today. You are the officer who caught this call at one in the morning. By the end of the block you are going to write the report.',
        'One thing before we start. Everything that happens after tonight — the arrest, the charge, the trial, whether somebody gets convicted or walks — all of it runs on the report you write. Not on what you remember. On what you wrote down.',
        'And you will never be in the room when it gets read. A detective reads it next week. A prosecutor reads it next month. A defence attorney reads it looking for a hole. A jury might read it in two years.',
        'You are not there to explain what you meant. So it has to work without you.',
      ],
    },
    {
      day: 'DAY 1', n: 2, min: '12–25', name: 'The walk-through',
      cue: 'Incident Report form up on the board. They are looking, not writing.',
      lines: [
        'Open the Incident Report. Do not write anything yet, just look at it.',
        'Five blocks. Block 1 is administrative — when, where, what kind of call. Block 2 is persons, everybody involved and how to find them again. Block 3 is property and evidence. Block 4 is the narrative, that is the story. Block 5 is status, which is just: is this case finished or not.',
        'Every block has one job. If you put something in the wrong block, the person who needs it will not find it. That is the whole reason the form looks like this.',
      ],
    },
    {
      day: 'DAY 1', n: 3, min: '25–35', name: 'Handing off to Ray',
      cue: 'Switch the board to the Case File. Pick a reader before you start.',
      lines: [
        'Now the Case File. This is everything you know. There is no more.',
        '[Student reads the dispatch box, then all four of Delgado’s paragraphs. Slowly.]',
        'Okay. Again.',
        'And this time, listen for what he does not say.',
        '[Second read. Do not comment between them.]',
      ],
    },
    {
      day: 'DAY 1', n: 4, min: '35–42', name: 'The model — Block 1 together',
      cue: 'You are filling Block 1 on the board with them. The whole point is the offence-type argument. Let it run.',
      lines: [
        'Block 1, with me. Case number — we were not given one, leave it. Date and time reported — that is in the dispatch box, not from Ray.',
        'Offence type. What is this?',
        '[Somebody says burglary. They always do.]',
        'Prove it. Burglary needs two things: somebody got in, and they got in intending to commit a crime. Which sentence in the Case File proves somebody got in?',
        '[Let them hunt. There is not one.]',
        'Nobody saw anybody. Ray never went in the room. So what can you actually write?',
        '[Take suggestions until you land on something defensible.]',
        'Here is the rule for the rest of the day. If you cannot support the word, you do not get to use the word.',
      ],
    },
    {
      day: 'DAY 1', n: 5, min: '42', name: 'SEND-OFF — Assignment 1',
      sendoff: true,
      cue: 'Turning them loose on the Incident Report form. Thirty minutes.',
      lines: [
        'You have got thirty minutes. Blocks 1 through 5.',
        'Two rules.',
        'One. Only what is in the Case File. If it is not on that page, you do not know it.',
        'Two. If you cannot fill a field, leave it blank. Do not guess, do not estimate, do not write “unknown” unless you actually mean it. Blank is a real answer.',
        'And somebody is going to put their hand up and ask me “can I just put —” and the answer is no. Leave it blank.',
        'Go.',
      ],
    },
    {
      day: 'DAY 1', n: 6, min: '72', name: 'The turn — page two',
      cue: 'Stop the room. This is the real assignment and most of them think they are nearly done.',
      lines: [
        'Hands up off the keyboards. Go to page two.',
        'Look at every blank you left. Every one of those is a question somebody has to answer before this case goes anywhere at all.',
        'Three columns. What you could not establish. Who would know it. How you would get it.',
        'This page is worth as much as the report. An officer who knows what is missing is doing the job. An officer who filled the blanks in with guesses just lost the case.',
      ],
    },
    {
      day: 'DAY 1', n: 7, min: '84–90', name: 'The close',
      cue: 'Collect gaps out loud and write them on the board. Leave them up if you can.',
      lines: [
        'Four people, one gap each, out loud.',
        '[Write each one on the board as they say it.]',
        'Look at that list. Thursday you get an interview — the operations supervisor, Ray’s boss. She can answer some of this.',
        'But you only get answers to the questions you actually write down. So bring that page.',
      ],
    },

    /* -------- DAY 2 \u2014 as actually run: the interview, then the supplemental */
    {
      day: 'DAY 2', n: 8, min: '0\u20138', name: 'The intro',
      cue: 'Do-now. They reopen Day 1\u2019s page two.',
      lines: [
        'Pull up your report from last time, page two. Circle your three worst holes \u2014 the three things that bother you most about your own report.',
        'Those three are what today is for. You get one interview. Marisa Vance, operations supervisor. Ray\u2019s boss.',
        'One interview. That is it. No second go, no follow-up call.',
      ],
    },
    {
      day: 'DAY 2', n: 9, min: '8\u201318', name: 'How to ask',
      cue: 'Mini-lesson off the five rules on file 3. Do the door example on the board.',
      lines: [
        'Before you talk to her you have to know how to ask. Four things.',
        'First. Open, not closed. Watch \u2014 \u201cWas the door forced open?\u201d What do I get? Yes or no. Now \u2014 \u201cDescribe the door.\u201d What do I get? A paragraph. Same information. One question actually gets it.',
        'Second. One fact per question. Ask two things at once and you get one answer, and you will not know which one she answered.',
        'Third, and this is the big one. Never put the answer in the question. If I say \u201cthere were about ten laptops in there, right?\u201d \u2014 she can just agree with me. And now there is a number in my report that I made up myself. I did not learn anything. I contaminated my own case.',
        'Fourth. Always ask how she knows. Every fact in your report needs a source. \u201cVance stated she counted them Friday afternoon\u201d is evidence. \u201cThere were nine laptops\u201d is just a sentence.',
      ],
    },
    {
      day: 'DAY 2', n: 10, min: '18', name: 'SEND-OFF \u2014 Assignment 2a',
      sendoff: true,
      cue: 'Interview Preparation, file 3. They submit before anything else happens.',
      lines: [
        'Interview Preparation is open in Canvas. You have got until the half hour.',
        'Work down your gap list. For each hole, write the question. Write it out in full, the way you would actually say it to her.',
        'Then submit it.',
        'And here is the part you need to hear. You are not getting her statement until your questions are in. Weak questions, weak information. That is not me being awkward, that is the job.',
        'Go.',
      ],
    },
    {
      day: 'DAY 2', n: 11, min: '26', name: 'The gate',
      cue: 'Hold this. Do not publish assignment 2b until submissions are in. The whole lesson hangs here.',
      lines: [
        'Pencils down. Submit. Everybody in?',
        '[Check Canvas. Actually check. Then publish assignment 2b and put file 4 on the board.]',
        'Okay. Here is what she said.',
      ],
    },
    {
      day: 'DAY 2', n: 12, min: '28\u201334', name: 'Handing off to Vance',
      cue: 'Read all seven paragraphs straight through. Do not comment while you read.',
      lines: [
        'I am going to read this straight through. Do not write yet. Just listen.',
        '[Read all seven paragraphs. No commentary, no eyebrows, nothing.]',
        'Now look at your question sheet. Some of what you asked is in there. Some of it is not \u2014 and that is also information.',
      ],
    },
    {
      day: 'DAY 2', n: 13, min: '34\u201358', name: 'SEND-OFF \u2014 Assignment 2b',
      sendoff: true,
      cue: 'File 5, Blocks 1 to 3. Twenty-four minutes. Block 3 is the one that was empty last time.',
      lines: [
        'Supplemental Report. A supplement adds to your original report. It does not repeat it and it does not replace it. New information only.',
        'Blocks 1 and 2 are fast \u2014 case number, who you interviewed, when and where. Three minutes.',
        'Block 3 is the real one. Property, access and keys, timeline, scene and surveillance. That property block was empty last time. You can fill it now \u2014 nine laptops, Dell, asset tags, what they cost.',
        'And every single line gets a name on it. \u201cVance stated.\u201d Not \u201cit was.\u201d',
        'Leave the Conflicting Information block alone for now. We do that one together.',
        'Go.',
      ],
    },
    {
      day: 'DAY 2', n: 14, min: '58\u201368', name: 'The contradiction',
      cue: 'Stop the room BEFORE they fill that block. Both accounts on the board. This is the most valuable ten minutes of the unit.',
      lines: [
        'Stop. Everybody look up.',
        '[Put both lines on the board, side by side.]',
        'Delgado told you the back door should not be unlocked after ten.',
        'Vance told you it is on a timer that locks at nine \u2014 but that it does not always catch, and she has put in two work orders nobody answered.',
        'Those do not match. So which one of them lied to you?',
        '[Take it. Let them argue. Then land it.]',
        'Neither. Neither one of them lied to you. They each know a piece of it. Ray knows the rule. Vance knows the rule and she knows the door is broken.',
        'You do not get to pick a winner. You are not the judge and you are not the jury. You write both, you put a name on each one, and you let the investigation sort it out.',
        'Now fill in the Conflicting Information block. Both columns, then the one sentence you would actually put in the report.',
      ],
    },
    {
      day: 'DAY 2', n: 15, min: '68\u201380', name: 'Leads, then what is still missing',
      cue: 'The last two sections of file 5. The distinction between a lead and a conclusion is the thing to hold them to.',
      lines: [
        'Leads for follow-up. A lead is an action \u2014 something a person can actually go and do. A name is not a lead.',
        'Then the last box. What you still cannot establish, and who or what would answer it.',
        'That was true on day one and it is still true. An officer who knows what is missing is doing the job.',
      ],
    },
    {
      day: 'DAY 2', n: 16, min: '80\u201388', name: 'Read a few out',
      cue: 'Out loud, from the room. Two or three students, one lead and one unresolved each.',
      lines: [
        'Give me one lead. Somebody else, one thing you still cannot establish.',
        '[Take three or four. Do not correct them in front of the room unless it is a conclusion dressed up as a lead \u2014 then ask what action it names.]',
      ],
    },
    {
      day: 'DAY 2', n: 17, min: '88\u201390', name: 'The close',
      cue: 'Two minutes. Name the arc, then let them go.',
      lines: [
        'That is a case. You took a call at one in the morning off one nervous witness. You wrote a report. You worked out what was missing. You interviewed somebody to close the gaps, and you documented it.',
        'One last thing. Nobody in this room charged anybody with anything today. That was never your job on the report.',
        'You wrote what happened. Somebody else decides what to call it.',
      ],
    },
  ],

  /* Off-script lines for the two things that reliably happen. */
  spotsHeading: 'If it comes up',
  spotsBlurb: 'These two happen in nearly every room. You do not have to go looking for them, but have the words ready.',
  spots: [
    {
      when: 'Somebody says Dontae Rivers did it.',
      lines: [
        'Read me the sentence that says he did it.',
        '[There is not one. She says “I am not saying this man did anything.”]',
        'She told you about him because you asked who has keys. And his key opened the building, not the equipment room — she said that too.',
        'So what is the lead? The lead is: find out whether that key ever came back. That is an action, somebody can go and do it.',
        '“He did it” is a conclusion. Conclusions do not go in reports.',
      ],
    },
    {
      when: 'Somebody is annoyed that the camera does not work.',
      lines: [
        'Good. You should be annoyed.',
        'She filed a work order in July and nobody came out. That is the most realistic sentence in the whole file.',
        'Half of investigation is finding out that the thing which would have answered your question was broken, or not switched on, or nobody kept it. You write that down too — that the camera was inoperative and when it was reported. That is a fact about the case.',
      ],
    },
  ],
};
