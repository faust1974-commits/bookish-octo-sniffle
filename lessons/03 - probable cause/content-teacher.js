module.exports = {
  title: 'Run Sheet',
  subtitle: 'Probable Cause · one 90-minute block',

  standards: [
    ['CJO 2', '13.09 evaluating a report prior to submission · 13.10 identify and locate state statutes · 13.11 define and write a probable-cause affidavit'],
    ['CJO 3', '17.01 levels of proof in investigations'],
    ['CJO 1', '03.04 identify elements of criminal law · 03.07 misdemeanour and felony procedures in Florida'],
  ],

  bigIdea: 'Up to now they have been recording what happened. Today what they write can take somebody’s liberty. The affidavit is where report writing stops being an exercise — and the lesson lands because the case gives them probable cause for theft and still refuses to give them burglary.',

  prep: [
    'One Canvas assignment with file 1 (pawn record) attached but <strong>unpublished</strong>, and a second with file 2 (worksheet) published from the start — they need Parts A and B before the record drops.',
    'Students need their incident report and supplemental report from last week. Remind them in the Canvas description.',
    'Open file 1 from OneDrive for the board, not the Canvas preview.',
    'Chromebooks need flsenate.gov reachable. <strong>Check this before first period</strong> — if your filter blocks it, Part B has to come off the devices and onto the board.',
  ],

  grading: [
    '<strong>Grade Part C, the elements table.</strong> It is the only part where you can see the reasoning. Five rows, fifteen seconds a student.',
    '<strong>Then read Part E’s burglary question.</strong> One short answer, and it tells you whether the whole unit landed.',
    '<strong>Do not grade the sworn statement for prose.</strong> You already graded narrative writing last week.',
  ],

  script: [
    {
      n: 1, min: '0–8', name: 'The intro',
      cue: 'They are seated with last week’s report open. File 1 is NOT out yet.',
      lines: [
        'Get last week’s report out — both of them, the incident report and the supplemental. Read your own narrative back to yourself.',
        'Everything you have written in here so far did one job: it recorded what happened.',
        'Today is different. Today you write a document that you sign under oath, and a judge reads it to decide whether somebody goes to jail.',
        'You do not get to be approximately right on this one.',
      ],
    },
    {
      n: 2, min: '8–22', name: 'The ladder',
      cue: 'Levels of proof. It is on their worksheet. Build it on the board from the bottom up.',
      lines: [
        'Every single thing an officer does requires a level of proof, and you cannot swap one for another.',
        'Bottom rung. A hunch. You think something is off and you cannot say why. What does a hunch let you do? Nothing. Not one thing.',
        'Next. Reasonable suspicion. Now you can point at specific facts and put them into words. That lets you stop somebody briefly and investigate. It does not let you arrest them.',
        'Next. Probable cause. Facts that would make a reasonable person believe a crime happened and that this person did it. That is arrest. That is a search warrant. That is a charge.',
        'Then preponderance of the evidence, which is civil court, more likely than not. And at the very top, beyond a reasonable doubt — and that one is never yours. That belongs to twelve people in a box.',
        'You are writing at probable cause today. One rung. Not the one below it and not the one above it.',
      ],
    },
    {
      n: 3, min: '22–32', name: 'SEND-OFF — Part A',
      sendoff: true,
      cue: 'Report review, on their own work. Ten minutes. The last question is the one that matters.',
      lines: [
        'Worksheet, Part A. Ten minutes. Run the checklist against your own report, honestly — nobody is marking the boxes.',
        'Then two written questions. First, the one thing you would change about your report now that you have read it back.',
        'Second one, and think about this. Before today, against a named person, where was this case on the ladder?',
        '[Let them answer it themselves. The honest answer is nowhere — there was no named person at all.]',
        'Go.',
      ],
    },
    {
      n: 4, min: '32–40', name: 'THE DROP — the pawn record',
      cue: 'Publish file 1 and put it on the board. Do not explain it. Let them find the asset tags themselves.',
      lines: [
        'Stop. Something came back.',
        'Three days after you filed your report, you ran the asset tags from your own supplemental report through the pawn database. Pawnbrokers have to record every transaction and report it. That is why this search is even possible.',
        'Two of the nine came back.',
        '[Put file 1 on the board. Say nothing. Wait for somebody to read the asset tags out loud.]',
        'CC-0043 and CC-0047. Where did those numbers come from?',
        '[They wrote them down last week, off Vance. Let that land.]',
        'That is why you write the tags down. A year from now that is the only reason this case closes.',
        'Now — where are we on the ladder? Has it moved?',
      ],
    },
    {
      n: 5, min: '40–52', name: 'SEND-OFF — Part B, find the law',
      sendoff: true,
      cue: 'Chromebooks. flsenate.gov. Twelve minutes. Do not give them the number.',
      lines: [
        'Part B. Twelve minutes, on your devices.',
        'A report describes what happened. A charge has to name a statute — and nobody is going to hand you the number. Finding it is the job, and you will do it this way for the rest of your career.',
        'flsenate.gov. Laws, then Florida Statutes. Chapter 812 — Theft, Robbery and Related Crimes. Find the section that defines theft.',
        'Read subsection one for what theft is. Then subsection two, because the degree changes with the value.',
        'Nine laptops at about five hundred and twenty dollars. Do the arithmetic, then find the tier your total falls into. And copy the statute’s exact words — do not paraphrase a law you are about to swear to.',
        'Go.',
      ],
    },
    {
      n: 6, min: '52–62', name: 'Part C — element by element',
      cue: 'The intellectual core of the lesson. Model one row on the board before they work.',
      lines: [
        'Part C, and this is the part that matters most today.',
        'A statute is a list of parts. Lawyers call them elements. Every part has to be matched to a fact, and every fact has to come from somewhere in your file.',
        '[Model one row on the board.]',
        'Say the statute requires that the property belonged to somebody else. What fact satisfies that? Vance said she bought them in February and she keeps the inventory. Where did that come from? Vance statement. That is a complete row.',
        'Now you do the rest. And if you cannot fill a row — stop and look at that. A row you cannot fill means you do not have probable cause. You have a theory.',
      ],
    },
    {
      n: 7, min: '62–80', name: 'SEND-OFF — Part D, the affidavit',
      sendoff: true,
      cue: 'Eighteen minutes. Short and sworn. Do not let them retell the whole narrative.',
      lines: [
        'Part D. Eighteen minutes. This is the affidavit.',
        'Defendant, charge, when, where, and then the sworn statement.',
        'The sworn statement is short. Eight to twelve sentences. You are not retelling your narrative — you already wrote that. You are walking a judge from your report, to the asset tags, to the pawn record, and then you stop.',
        'Name your source for every fact. And look at the identification line — what specifically ties that name to those two laptops? That is the first sentence a defence attorney goes after. Make it hold.',
        'Then sign the oath block. Read what you are signing before you sign it.',
        'Go.',
      ],
    },
    {
      n: 8, min: '80–88', name: 'The landing — the burglary question',
      cue: 'Stop the room. This is the whole unit in six minutes. Take the argument.',
      lines: [
        'Pencils down. Part E.',
        'The call came in as a burglary. You have been looking at the word burglary for two weeks.',
        'Burglary requires proof that somebody entered that building unlawfully. So — do you have probable cause to charge Rivers with burglary?',
        '[Take it. Let them argue both sides. Somebody will say yes.]',
        'Walk me through it. You have two laptops in a pawn shop with his thumbprint on the form. What does that prove? It proves he had them.',
        'Does it prove he went in that building? Did anybody see him there? Did anybody see anybody? Was the camera working?',
        'You have probable cause for theft. You do not have it for burglary. Same case, same person, two different answers — because they are two different statutes with two different lists of elements.',
        'And that is why you did not get to write the word burglary in your report two weeks ago. Not because I was being difficult. Because it was never established.',
        'Fill in Part E. Say what you cannot prove and what it would take. Then submit.',
      ],
    },
    {
      n: 9, min: '88–90', name: 'The close',
      cue: 'Two minutes. Name the arc, then let them go.',
      lines: [
        'Look at what you did across two weeks. You took a call at one in the morning off one nervous witness. You worked out what was missing. You interviewed somebody to close the gaps. You wrote down nine asset tags that did not seem to matter.',
        'And one of those numbers is the reason you have a suspect at all.',
        'Seven of those laptops are still out there. The case is still open. That is the normal condition of police work — not solved, not closed, just honestly documented.',
      ],
    },
  ],

  spotsHeading: 'If it comes up',
  spots: [
    {
      when: 'A student insists this is burglary because he obviously broke in.',
      lines: [
        'Obviously is not an element. Read me the element.',
        'You have to prove entry. Who saw him enter? Nobody saw anybody — that has been true since the first night.',
        'You might be right about what happened. You are almost certainly right. But a charge is not about what you believe, it is about what you can prove, and a judge will throw out what you cannot.',
        'This is why burglary cases live and die on cameras, prints and keys — and we have a dead camera, no prints yet, and a key she cannot account for.',
      ],
    },
    {
      when: 'Somebody asks why he only got sixty dollars for a five-hundred-dollar laptop.',
      lines: [
        'Good question, and you can put it in your report as an observation. What you cannot do is write down what it means.',
        'You may write: the pawn record shows sixty dollars advanced against each unit. That is a fact.',
        'You may not write: he sold them cheap because he knew they were stolen. That is a conclusion, and you did not see inside his head.',
        'A prosecutor can argue that later. You just hand them the number.',
      ],
    },
    {
      when: 'A student asks whether the thumbprint proves it.',
      lines: [
        'It proves he stood at that counter and signed that form. That is not nothing — it is a strong identification and it is exactly what you want in the affidavit.',
        'It does not prove where he got them. Keep those two things separate, because the affidavit has to.',
      ],
    },
  ],

  answerKeyHeading: 'Where the lesson is meant to land',
  answerKey: [
    ['PART A', 'The honest answer to “where was this case on the ladder?” is: nowhere, against a named person — there was no named person. Against the building, you had a crime but no suspect.'],
    ['PART B', 'Chapter 812, the theft section. Nine units at about $520 is roughly $4,680, which falls in the tier running from $750 up to $5,000. Have them quote the statute’s own words rather than take your number for it — that is the benchmark.'],
    ['PART C', 'Rows should source to: Vance for ownership and value, the asset tags for identity of the property, the pawn record for possession and identification, Delgado and the dispatch entry for the time window.'],
    ['PART D', 'Watch the identification line. The strong answer names the asset tags matching Vance’s inventory PLUS the licence and thumbprint on the pawn form. A weak answer just says “he pawned them”.'],
    ['PART E', 'No probable cause for burglary — no proof of entry, nobody saw anybody, the camera was inoperative. What it would take: prints from the equipment room, a working camera, the recovered key, or a witness. Possession is not entry.'],
  ],
};
