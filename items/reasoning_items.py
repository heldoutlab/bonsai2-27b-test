"""Fresh multi-step reasoning items (R01-R40) plus pilot items (RP1-RP4).

Written from scratch for the bonsai2 pre-registered comparison; never published.
Every key is recomputed by brute force / simulation in reasoning_solvers.py.

answer_type:
  int  - a single integer
  str  - a single word / token, compared case-insensitively after stripping
  list - comma-separated values in the order the prompt specifies
"""

ITEMS = [
    # ---------------------------------------------------------------- kind 1
    {
        "id": "R01",
        "prompt": '''Six traders - Bascom, Dunmore, Ilka, Oriel, Thessaly and Wren - each rent one of the six stalls that stand in a single row at the Pellam night market. The stalls are numbered 1 to 6 from west to east, one trader per stall. Two stalls are "adjacent" when their numbers differ by exactly 1.

1. Oriel's stall is somewhere west of Bascom's.
2. Thessaly's stall is immediately east of Wren's.
3. Dunmore is not in stall 1 or stall 6.
4. Exactly one stall lies between Ilka's stall and Oriel's stall.
5. Bascom's stall is not adjacent to Dunmore's.
6. Wren is in an even-numbered stall.
7. Ilka's stall is not adjacent to Wren's.

Who is in each stall?

Finish with a final line of the form "ANSWER: <the six names in stall order from stall 1 to stall 6, comma-separated>"''',
        "answer": "Ilka,Dunmore,Oriel,Wren,Thessaly,Bascom",
        "answer_type": "list",
    },
    {
        "id": "R02",
        "prompt": '''A craft hall runs five evening workshops next week, exactly one per evening from Monday to Friday: Fermenting, Glazing, Knotwork, Mapmaking and Whittling. Each workshop is led by a different tutor: Anselm, Brisa, Corwin, Delphine and Eskil.

1. Mapmaking is held later in the week than Glazing and earlier in the week than Whittling.
2. Brisa's workshop is on the evening immediately after Corwin's.
3. Delphine leads neither Glazing nor Fermenting.
4. Knotwork is on Wednesday or Friday.
5. Exactly one of these two statements is true: "Eskil teaches on Monday"; "Eskil leads Whittling".
6. Anselm's workshop takes place exactly two evenings after Fermenting (for example, Monday and Wednesday are two evenings apart).
7. Corwin does not lead Mapmaking.
8. Delphine's workshop is earlier in the week than Corwin's.

Which tutor teaches on each evening?

Finish with a final line of the form "ANSWER: <the five tutors' names in order from Monday to Friday, comma-separated>"''',
        "answer": "Eskil,Delphine,Corwin,Brisa,Anselm",
        "answer_type": "list",
    },
    {
        "id": "R03",
        "prompt": '''Seven councillors - Hask, Ione, Jorvik, Kestrel, Lumen, Marit and Nyle - sit at a round table with seven seats numbered 1 to 7 going clockwise, one person per seat. Seat 7 is next to seat 1. Two people are "adjacent" when they are in neighbouring seats. "k seats clockwise from X" means: start at X's seat and count k seats onward in the direction of increasing seat numbers, wrapping from 7 round to 1.

1. Hask is in seat 1.
2. Jorvik sits one seat clockwise from Marit.
3. Kestrel is not adjacent to Hask.
4. Lumen sits three seats clockwise from Ione.
5. Nyle is adjacent to Kestrel.
6. Ione is adjacent to neither Jorvik nor Hask.

Who sits in each seat?

Finish with a final line of the form "ANSWER: <the seven names in seat order from seat 1 to seat 7, comma-separated>"''',
        "answer": "Hask,Nyle,Kestrel,Ione,Marit,Jorvik,Lumen",
        "answer_type": "list",
    },
    {
        "id": "R04",
        "prompt": '''Nine tiles numbered 1 to 9 are laid on a board of three rows and three columns, one tile per square, each number used exactly once. The rows are called top, middle and bottom; the columns are called left, centre and right. The "centre tile" is the one in the middle row and centre column.

1. The three tiles in the top row add up to 13.
2. Going down the left column the numbers strictly increase: top-left is less than middle-left, which is less than bottom-left.
3. The three tiles in the bottom row add up to 15.
4. The centre tile equals the top-left tile plus the bottom-right tile.
5. Tile 2 is in the square directly below tile 8 (same column, next row down).
6. Tiles 1 and 3 are in the same column.

Which tiles are in the middle row?

Finish with a final line of the form "ANSWER: <the three numbers of the middle row from left to right, comma-separated>"''',
        "answer": "6,9,2",
        "answer_type": "list",
    },
    {
        "id": "R05",
        "prompt": '''Six volunteers - Pavel, Quill, Rosalind, Soren, Tamsin and Ulrich - will staff a lookout tower tomorrow. There are three shifts, in this order through the day: dawn, noon, dusk. Each shift is worked by exactly two volunteers and each volunteer works exactly one shift.

1. Pavel and Quill are on different shifts.
2. Rosalind's shift is earlier in the day than Soren's.
3. If Tamsin works the dusk shift, then Ulrich works the dawn shift.
4. Quill does not work the noon shift.
5. If Pavel works the dawn shift, then Rosalind works the noon shift.
6. Exactly one of these two statements is true: "Ulrich and Soren share a shift"; "Tamsin and Pavel share a shift".
7. Tamsin does not work the dawn shift.

Which two volunteers work the dusk shift?

Finish with a final line of the form "ANSWER: <the two names of the dusk-shift volunteers in alphabetical order, comma-separated>"''',
        "answer": "Quill,Soren",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 2
    {
        "id": "R06",
        "prompt": '''Three bins hold bolts: Amber holds 17, Cobalt holds 8 and Slate holds 23. Carry out the following steps in order. "Fullest" means the bin holding the most bolts at that moment and "emptiest" means the bin holding the fewest at that moment (whenever these words are used there is no tie).

1. Move half of Slate's bolts into Amber (if Slate's count is odd, round the half down).
2. Move 5 bolts from Amber to Cobalt.
3. Move 6 bolts from the fullest bin to the emptiest bin.
4. Swap the entire contents of Amber and Cobalt.
5. Move one third of Cobalt's bolts, rounded down, into Slate.
6. Count the bolts in the emptiest bin; remove that many bolts from the fullest bin and throw them away.
7. If Amber now holds an odd number of bolts, move 3 bolts from Amber to Slate; otherwise move 4 bolts from Slate to Amber.
8. Move half of the fullest bin's bolts, rounded down, into the emptiest bin.

How many bolts does each bin hold at the end?

Finish with a final line of the form "ANSWER: <three integers: the final counts for Amber, Cobalt, Slate in that order, comma-separated>"''',
        "answer": "17,12,7",
        "answer_type": "list",
    },
    {
        "id": "R07",
        "prompt": '''A toy machine has four registers named P, Q, R and S. They start with P = 3, Q = 14, R = 0 and S = 1. The machine executes the numbered lines below one after another, starting at line 1 and continuing to the next line unless a line tells it to jump. Every line uses the registers' current values.

1. Add P to R.
2. Add 2 to P.
3. Multiply S by 3.
4. If S is greater than 20, subtract 20 from S.
5. Subtract 3 from Q.
6. If Q is greater than 0, jump back to line 1.
7. If R is even, replace R by half of R; otherwise add S to R.
8. Replace P by P + R - Q.
9. Stop.

What value does register P hold when the machine stops?

Finish with a final line of the form "ANSWER: <a single integer, the final value of P>"''',
        "answer": "52",
        "answer_type": "int",
    },
    {
        "id": "R08",
        "prompt": '''Seven crates stand in a row. Positions are numbered 1 (far left) to 7 (far right). At the start the crates' labels, from position 1 to position 7, are: F, K, M, P, T, V, Z. In every step, position numbers refer to the row as it stands at that moment. Carry out these steps in order:

1. Swap the crates at positions 2 and 6.
2. Take the crate at position 1 and put it at the right end (the others each shift one place left).
3. Reverse the order of the crates in positions 3 to 6 inclusive.
4. Swap crate M with the crate immediately to its right (if M is at position 7, swap it with the crate at position 1 instead).
5. Take the crate at position 5 and put it at the left end.
6. Swap crate T with whichever crate is at position 4 (if T is already at position 4, do nothing).
7. Reverse the order of the crates in positions 1 to 3 inclusive.
8. Swap crate K with the crate immediately to its left (if K is at position 1, swap it with the crate at position 7 instead).
9. Take the crate at position 2 and put it at the right end.

What is the final order?

Finish with a final line of the form "ANSWER: <the seven labels from position 1 to position 7, comma-separated>"''',
        "answer": "Z,M,K,T,P,F,V",
        "answer_type": "list",
    },
    {
        "id": "R09",
        "prompt": '''A clerk processes numbered cards one at a time, in this order: 6, 3, 10, 7, 15, 4, 9, 12, 5, 16, 11, 8. She stacks cards on a tray (only the tray's top card can be looked at or removed); the tray starts empty. She also keeps a tally, which starts at 0. For each incoming card, call its number c and do the following:

(a) If the tray is empty, put c on the tray and move on to the next incoming card.
(b) Otherwise let t be the number on the tray's top card, and apply the one case that fits:
- c is greater than t, and exactly one of c and t is odd: remove the top card from the tray, add t to the tally, and go back to (a) with the same card c.
- c is greater than t, and c and t are both odd or both even: put c on top of the tray and move on.
- c is less than t, and c is even: put c on top of the tray and move on.
- c is less than t, and c is odd: discard c, add 1 to the tally, and move on.

After the last card has been processed, what is the tally plus the sum of the numbers on all cards still on the tray?

Finish with a final line of the form "ANSWER: <a single integer>"''',
        "answer": "76",
        "answer_type": "int",
    },
    {
        "id": "R10",
        "prompt": '''Red and Blue play a game on a circular track of ten squares numbered 0 to 9; moving forward from square 9 leads to square 0. Both tokens start on square 0 and both players start with 0 coins. They take turns, Red first. On a turn the player moves their own token forward by the number rolled and then applies these three rules in this order:

1. Lap bonus: if the move passed over square 0 or ended on square 0, the player gains 4 coins. (Merely starting a move from square 0 does not count.)
2. Square effect: ending on square 2, 3, 5 or 7 gains the player that many coins (the square's number). Ending on square 0, 4 or 8 costs the player 3 coins, or all their coins if they have fewer than 3. Squares 1, 6 and 9 do nothing.
3. Raid: if the player's token is now on the same square as the opponent's token, the player takes 2 coins from the opponent (or all of the opponent's coins if the opponent has fewer than 2).

The twelve rolls, in the order they are used (Red, Blue, Red, Blue, and so on), are: 3, 5, 4, 2, 6, 4, 2, 6, 5, 1, 4, 3.

How many coins does each player have after the twelfth roll?

Finish with a final line of the form "ANSWER: <two integers: Red's coins then Blue's coins, comma-separated>"''',
        "answer": "18,26",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 3
    {
        "id": "R11",
        "prompt": '''A lighthouse keeper's oil tank can hold at most 40 litres, and it holds exactly 40 litres on the morning of day 1. Every night the lamp burns oil: 7 litres on the night of each odd-numbered day and 5 litres on the night of each even-numbered day. A supply boat calls on the afternoon of every day whose number is a multiple of 4 (days 4, 8, 12, and so on), before that night's burning, and pours 20 litres into the tank - except that the tank can never hold more than 40 litres, so any oil that does not fit is taken away again. No other oil arrives.

On which day does the keeper, for the first time, have less oil in the tank at nightfall than the lamp needs for that night?

Finish with a final line of the form "ANSWER: <a single integer, the day number>"''',
        "answer": "27",
        "answer_type": "int",
    },
    {
        "id": "R12",
        "prompt": '''The Vellish calendar has five months in every year, in this order and with these lengths: Frostwane (31 days), Budrise (29 days), Highsun (33 days), Reaptide (30 days) and Duskfall (28 days). In any year whose number is divisible by 3, Duskfall has 29 days instead of 28; nothing else changes. The Vellish week has six days, in this order: Aln, Bru, Cey, Dov, Eth, Fen. After Fen comes Aln again, and the weeks run on without a break across month ends and year ends.

The 1st of Frostwane in the year 412 is a Cey. The harvest fair is held every year on the third Eth of Reaptide (the third day of that month that is an Eth).

On which day of the month of Reaptide does the harvest fair fall in the year 415?

Finish with a final line of the form "ANSWER: <a single integer, the day of the month>"''',
        "answer": "14",
        "answer_type": "int",
    },
    {
        "id": "R13",
        "prompt": '''At 06:00 there are 47 carts waiting on the north bank of a river. From then on one more cart arrives at the north bank every 3 minutes (at 06:03, 06:06, 06:09, and so on). A single ferry leaves the north bank at 06:00 and then again every 24 minutes (06:24, 06:48, and so on); 24 minutes is the time it needs to cross, unload and come back empty. Loading takes no time, and a cart that arrives at the exact minute of a departure can board that departure. The ferry always takes as many waiting carts as it has room for. It normally has room for 14 carts, but on every third departure (the 3rd, 6th, 9th, and so on) it also carries a mail wagon and has room for only 10 carts.

Counting the 06:00 departure as the 1st, which departure is the first one that leaves no cart waiting behind on the north bank, and how many carts are on board for that departure?

Finish with a final line of the form "ANSWER: <two integers: the departure number, then the number of carts on board, comma-separated>"''',
        "answer": "8,13",
        "answer_type": "list",
    },
    {
        "id": "R14",
        "prompt": '''A print shop prices every order separately. An order costs a fixed setup fee of 40 coins, plus 9 coins for each of the first 20 posters in the order, 7 coins for each of the 21st to 50th posters in the order, and 5 coins for each poster beyond the 50th.

Two clubs each placed one order of their own. Together the two orders contained 96 posters, the two orders were of different sizes, and the bill for the larger order was exactly 184 coins more than the bill for the smaller order.

How many posters were in the smaller order, and how many coins in total would the two clubs have saved if, instead of their two separate orders, they had placed one single combined order for all 96 posters?

Finish with a final line of the form "ANSWER: <two integers: the number of posters in the smaller order, then the coins saved, comma-separated>"''',
        "answer": "33,146",
        "answer_type": "list",
    },
    {
        "id": "R15",
        "prompt": '''A mosaic needs exactly 1000 tiles, and three people work on it.

Ada lays 24 tiles every day, starting on day 1.

Ben lays 30 tiles on each day he works. His first working day is day 4, and from then on he repeats a cycle of two working days followed by one rest day: he works on days 4 and 5, rests on day 6, works on days 7 and 8, rests on day 9, and so on.

Cyd lays 18 tiles on each day she works. She works only on even-numbered days, and her first working day is day 8.

Work stops the moment the 1000th tile is laid. On which day is the 1000th tile laid, and how many tiles were still needed at the start of that day?

Finish with a final line of the form "ANSWER: <two integers: the day number, then the number of tiles still needed at the start of that day, comma-separated>"''',
        "answer": "22,10",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 4
    {
        "id": "R16",
        "prompt": '''On the island of Quell every person belongs to exactly one of two clans. Embers make only true statements in the morning and only false statements in the afternoon. Tides do the opposite: they make only false statements in the morning and only true statements in the afternoon.

Five islanders - Avel, Brom, Cass, Dita and Eddo - each make one statement within the same minute, so it is either morning for all five statements or afternoon for all five.

Avel: "It is morning."
Brom: "Avel is a Tide."
Cass: "Dita and Brom belong to different clans."
Dita: "It is afternoon, and Cass is an Ember."
Eddo: "Cass is a Tide."

Which of the five are Embers?

Finish with a final line of the form "ANSWER: <the names of all the Embers among the five, in alphabetical order, comma-separated>"''',
        "answer": "Avel,Eddo",
        "answer_type": "list",
    },
    {
        "id": "R17",
        "prompt": '''Four heralds - Fenn, Gilda, Horst and Ines - each make exactly two statements. Exactly one of the four is a Truthsayer (both statements true), exactly one is a Liar (both statements false), and the other two are Switchers: a Switcher makes exactly one true statement and exactly one false statement, in either order.

Fenn: "Gilda is the Liar." "I am not the Liar."
Gilda: "Horst is the Liar." "Fenn is a Switcher."
Horst: "Ines is the Truthsayer." "Gilda is a Switcher."
Ines: "Fenn is the Truthsayer." "Horst is not a Switcher."

Which herald is the Liar?

Finish with a final line of the form "ANSWER: <one name, the herald who is the Liar>"''',
        "answer": "Horst",
        "answer_type": "str",
    },
    {
        "id": "R18",
        "prompt": '''Five sealed chests are numbered 1 to 5. Exactly one of them contains the royal seal. Each chest bears one inscription, and exactly two of the five inscriptions are true; the other three are false. Wherever "or" is used it is inclusive (one or both), and an "and" statement is true only if both of its parts are true.

Chest 1: "The seal is in chest 2 or chest 4."
Chest 2: "The seal is not in chest 1, and the inscription on chest 4 is false."
Chest 3: "The seal is in an odd-numbered chest."
Chest 4: "The seal is not in this chest, and the inscription on chest 1 is true."
Chest 5: "The seal is in this chest, or the inscription on chest 3 is false."

Which chest contains the seal?

Finish with a final line of the form "ANSWER: <a single integer from 1 to 5, the number of the chest holding the seal>"''',
        "answer": "3",
        "answer_type": "int",
    },
    {
        "id": "R19",
        "prompt": '''A control panel has six switches labelled A, B, C, D, E and F. Each switch is either up or down. The panel unlocks only for a setting that satisfies every one of the following rules. (An "if ... then ..." rule is broken only when its "if" part holds and its "then" part does not.)

1. If A is up, then C is down.
2. If B is up, then exactly one of A and D is up.
3. Exactly three of the six switches are up.
4. If C is down, then exactly one of E and F is up.
5. If A and B are both down, then F is down.
6. D and E are not both up.
7. At least one of B and D is up.
8. B and F are not both up.
9. C and E are either both up or both down.

Exactly one setting satisfies all nine rules. Which switches are up in it?

Finish with a final line of the form "ANSWER: <the letters of the switches that are up, in alphabetical order, comma-separated>"''',
        "answer": "A,D,F",
        "answer_type": "list",
    },
    {
        "id": "R20",
        "prompt": '''Five lodgers share a house: Vane, Wick, Xanthe, Yoren and Zell. Each of them is either a truth-teller, whose statement is true, or a liar, whose statement is false. Each makes exactly one statement, and "us" always means all five lodgers including the speaker.

Vane: "Exactly one of the five of us is a liar."
Wick: "Xanthe is a truth-teller."
Xanthe: "Wick and Yoren are of different types - one a truth-teller and the other a liar."
Yoren: "The number of liars among the five of us is even." (Zero would count as even.)
Zell: "At least four of the five of us are liars."

Which of the lodgers are liars?

Finish with a final line of the form "ANSWER: <the names of all the liars, in alphabetical order, comma-separated>"''',
        "answer": "Vane,Yoren,Zell",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 5
    {
        "id": "R21",
        "prompt": '''The strongroom at Carrow Mill is opened with a code of four digits entered one after another. Each digit is one of 1, 2, 3, 4, 5 or 6, and the same digit may appear more than once in a code as long as the rules below are respected. A code is called "valid" when it satisfies all three of these rules:

1. No two digits that are next to each other in the code are equal.
2. The first digit is strictly greater than the fourth digit.
3. The sum of the four digits is an even number.

How many different valid codes are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of valid codes>"''',
        "answer": "171",
        "answer_type": "int",
    },
    {
        "id": "R22",
        "prompt": '''An expedition crew of exactly 5 people is to be chosen from 12 candidates: 5 engineers (one of whom is named Ostra), 4 pilots (one of whom is named Penn) and 3 medics (one of whom is named Quay). All 12 candidates are different people, each has exactly one profession, and a crew is just a set of 5 people - the order of choosing does not matter.

A crew is acceptable only if all of the following hold:
1. It contains at least one engineer, at least one pilot and at least one medic.
2. Ostra and Penn are not both in it.
3. If Quay is in it, then it contains at least two pilots.

How many different acceptable crews are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of acceptable crews>"''',
        "answer": "380",
        "answer_type": "int",
    },
    {
        "id": "R23",
        "prompt": '''A courier walks through a street grid from the intersection (0,0) to the intersection (5,4). Each step takes the courier exactly one block east, which increases the first coordinate by 1, or exactly one block north, which increases the second coordinate by 1. Every route therefore consists of 9 steps: 5 east and 4 north.

Two intersections are closed and may not be visited at any point: (2,2) and (4,1).

In addition, the courier never makes three consecutive steps in the same direction; for example, east-east-east may not occur anywhere in the route, and neither may north-north-north.

How many different routes can the courier take?

Finish with a final line of the form "ANSWER: <a single integer, the number of allowed routes>"''',
        "answer": "12",
        "answer_type": "int",
    },
    {
        "id": "R24",
        "prompt": '''Twelve identical coins are to be placed into four chests that stand in a row and are labelled A, B, C, D from left to right. All twelve coins must be placed, and a chest may be left empty. The placement must obey all of these rules:

1. No chest holds more than 5 coins.
2. No two neighbouring chests hold the same number of coins. The neighbouring pairs are A and B, B and C, and C and D.
3. Chest A holds strictly more coins than chest D.

Two placements count as different when at least one chest holds a different number of coins. How many different placements are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of placements>"''',
        "answer": "36",
        "answer_type": "int",
    },
    {
        "id": "R25",
        "prompt": '''Seven different volumes are to be arranged in a single row on one shelf: three atlases (A1, A2, A3), two diaries (D1, D2) and two ledgers (L1, L2). All seven volumes are distinguishable from one another, so swapping two different volumes always gives a different arrangement. The arrangement must obey all of these rules:

1. No two atlases stand next to each other.
2. The two diaries stand next to each other (in either order).
3. Ledger L1 stands somewhere to the left of ledger L2 (they need not be next to each other).

How many different arrangements are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of arrangements>"''',
        "answer": "144",
        "answer_type": "int",
    },
    # ---------------------------------------------------------------- kind 6
    {
        "id": "R26",
        "prompt": '''The Lantern cipher encodes a word written in capital letters (A to Z) in three steps.

Step 1: Shift every letter forward in the alphabet by its position in the word: the first letter by 1, the second letter by 2, the third by 3, and so on. Shifting wraps around, so the letter after Z is A.

Step 2: In the result of step 1, swap the 1st and 2nd letters, swap the 3rd and 4th letters, swap the 5th and 6th letters, and so on. If the word has an odd number of letters, its last letter stays where it is.

Step 3: In the result of step 2, replace every vowel (A, E, I, O or U) by the next letter of the alphabet. Leave all other letters unchanged.

Encode the word HARVEST.

Finish with a final line of the form "ANSWER: <the encoded word: seven capital letters with no spaces>"''',
        "answer": "CJZVYJB",
        "answer_type": "str",
    },
    {
        "id": "R27",
        "prompt": '''A row of 12 lamps is numbered 1 to 12 from left to right. Each lamp is either ON (written 1) or OFF (written 0). A lamp's neighbours are the lamps immediately to its left and right; lamp 1 and lamp 12 each have only one neighbour.

The row changes in rounds. In each round all lamps change at the same moment, and every lamp looks only at how the row stood just before that round: a lamp flips (ON becomes OFF, OFF becomes ON) if exactly one of its neighbours was ON; otherwise it stays as it was.

The starting row, from lamp 1 to lamp 12, is: 0 1 1 0 1 0 0 1 1 1 0 0.

What does the row look like after 4 rounds?

Finish with a final line of the form "ANSWER: <the twelve digits (0 or 1) for lamps 1 to 12 in order, written together with no spaces or commas>"''',
        "answer": "001100110100",
        "answer_type": "str",
    },
    {
        "id": "R28",
        "prompt": '''"Tollgate ordering" rearranges and thins a list of positive whole numbers in three steps.

Step 1: Arrange the numbers by digit sum (the sum of a number's decimal digits), smallest digit sum first. Whenever two or more numbers have the same digit sum, the larger number goes before the smaller one.

Step 2: Look at the arrangement produced by step 1 and mark every number that is smaller than the number standing immediately before it. The first number has nothing before it and is never marked. All comparisons are made on the step-1 arrangement as it stands, before anything is removed.

Step 3: Remove all marked numbers, keeping the remaining numbers in their step-1 order.

Apply tollgate ordering to this list: 47, 130, 58, 92, 205, 76, 311, 64, 9, 83.

Finish with a final line of the form "ANSWER: <the numbers that remain after step 3, in their final order, comma-separated>"''',
        "answer": "130,311,64,92,76",
        "answer_type": "list",
    },
    {
        "id": "R29",
        "prompt": '''In the card game Quarrel every card has a rank from 1 to 9 and one of three suits: Moons, Suns or Stars. A hand of seven cards is scored by applying these rules in order, starting from 0 points:

1. Pairs: add 4 points for every pair of cards that have the same rank. (Three cards of one rank would make three pairs.)
2. Run: find the longest group of consecutive ranks that all appear in the hand; suits do not matter and a rank that appears twice counts once. If that group contains 3 or more ranks, add 2 points for each rank in it; otherwise add nothing.
3. Majority: if one suit has strictly more cards in the hand than each of the other two suits, add 1 point for each card of that suit. If two or more suits tie for the most cards, add nothing.
4. Penalty: subtract 2 points for every Stars card whose rank is odd.
5. Doubling: if the ranks of all seven cards add up to a multiple of 5, double the total reached after rules 1 to 4.

The hand is: 4 of Moons, 5 of Stars, 5 of Suns, 6 of Moons, 9 of Stars, 3 of Moons, 8 of Suns.

What is the hand's final score?

Finish with a final line of the form "ANSWER: <a single integer, the final score>"''',
        "answer": "22",
        "answer_type": "int",
    },
    {
        "id": "R30",
        "prompt": '''A string of letters is rewritten one step at a time using four rules, listed in priority order:

Rule 1: BB becomes A
Rule 2: AAA becomes C
Rule 3: AB becomes BA
Rule 4: CA becomes AC

Each step works like this. Find the lowest-numbered rule whose left-hand side occurs somewhere in the current string as a block of adjacent letters. Replace only the leftmost occurrence of that left-hand side with the rule's right-hand side. That completes one step; the next step starts again by checking Rule 1 first. The process stops when no rule's left-hand side occurs anywhere in the string.

The starting string is AABABBABAB.

What is the string when the process stops?

Finish with a final line of the form "ANSWER: <the final string, capital letters with no spaces>"''',
        "answer": "BACC",
        "answer_type": "str",
    },
    # ---------------------------------------------------------------- kind 7
    {
        "id": "R31",
        "prompt": '''Seven towns are joined by the following roads; each road can be travelled in both directions and its length is given in leagues. There are no other roads.

Alder - Brack: 4
Alder - Corrow: 7
Brack - Corrow: 2
Brack - Dellmoor: 9
Corrow - Esk: 5
Corrow - Dellmoor: 8
Dellmoor - Esk: 2
Dellmoor - Fenwick: 6
Esk - Grange: 10
Esk - Fenwick: 9
Fenwick - Grange: 3

A pedlar must travel from Alder to Grange and has a parcel to hand over in Dellmoor, so the route must pass through Dellmoor at some point. What is the total length, in leagues, of the shortest such route?

Finish with a final line of the form "ANSWER: <a single integer, the length of the shortest route from Alder to Grange that passes through Dellmoor>"''',
        "answer": "22",
        "answer_type": "int",
    },
    {
        "id": "R32",
        "prompt": '''Ten jobs labelled A to J must all be done. Their durations in hours are: A 4, B 6, C 3, D 5, E 2, F 7, G 4, H 3, I 5, J 2.

A job may start only when all of its prerequisites are finished. A and B have no prerequisites. C needs A. D needs A. E needs B and C. F needs C. G needs D and E. H needs F, G and J. I needs B. J needs D and I.

Two workers are available from hour 0. Each worker does one job at a time, each job is done by one worker, and a job once started runs without interruption until it is finished. The workers follow one fixed rule: whenever a worker is free and there is at least one unstarted job whose prerequisites are all finished, that worker immediately starts the one such job whose letter comes earliest in the alphabet. If both workers are free at the same moment, they take the two earliest such letters, one each (or the only one, if there is just one). A job that finishes at some moment counts as finished for jobs starting at that same moment. A worker waits only when no job is ready.

At what hour is the last job finished?

Finish with a final line of the form "ANSWER: <a single integer, the hour at which the last job finishes>"''',
        "answer": "25",
        "answer_type": "int",
    },
    {
        "id": "R33",
        "prompt": '''Eight villages are linked by the connections below. Each connection can be used in both directions and takes the stated number of hours. Three of the connections are ferry crossings, marked (ferry); the rest are roads. There are no other connections.

Ashford - Birle: 6
Ashford - Cranmer: 3 (ferry)
Birle - Dove: 7
Cranmer - Dove: 4
Cranmer - Elst: 11
Dove - Farrow: 2 (ferry)
Dove - Elst: 8
Elst - Gault: 5
Elst - Holm: 10
Farrow - Gault: 9
Farrow - Holm: 14
Gault - Holm: 3 (ferry)

A traveller going from Ashford to Holm holds a ticket that is good for one ferry crossing only, so the whole journey may include at most one ferry crossing (it may include none). What is the smallest possible total travel time in hours?

Finish with a final line of the form "ANSWER: <a single integer, the minimum number of hours from Ashford to Holm using at most one ferry crossing>"''',
        "answer": "24",
        "answer_type": "int",
    },
    {
        "id": "R34",
        "prompt": '''An old house has eight rooms: Atrium, Buttery, Cellar, Dormitory, Gallery, Hall, Library and Vault. The only ways between rooms are these:

- Passages without doors, usable in both directions: Atrium-Buttery, Atrium-Hall, Buttery-Cellar, Hall-Gallery, Cellar-Library.
- Hall-Library: a passage with a red door.
- Gallery-Dormitory: a passage with a blue door.
- Library-Vault: a passage with a green door.
- A laundry chute from the Dormitory down to the Cellar. It has no door but works in one direction only: from Dormitory to Cellar.

A passage with a coloured door can be used, in either direction, only by someone carrying the key of that colour. The red key lies in the Cellar, the blue key in the Library and the green key in the Dormitory. On entering a room you pick up any key lying there at once, which costs no move, and you keep every key for the rest of the journey.

You start in the Atrium carrying no keys. Each use of a passage or of the chute counts as one move. What is the smallest number of moves in which you can reach the Vault?

Finish with a final line of the form "ANSWER: <a single integer, the minimum number of moves from the Atrium to the Vault>"''',
        "answer": "9",
        "answer_type": "int",
    },
    {
        "id": "R35",
        "prompt": '''A piece of news spreads among nine villagers. Each villager has a fixed list of people they tell:

Arden tells Bex and Cole.
Bex tells Dara.
Cole tells Dara and Emrys.
Dara tells Finn.
Emrys tells Finn and Gwyn.
Finn tells Hale.
Gwyn tells Hale and Bex.
Hale tells Ivo.
Ivo tells nobody.

Arden first hears the news on day 1. Every villager passes the news on exactly once: on the day after the day on which they first heard it, they tell everyone on their list. A person who is told on some day and had not heard the news before counts as first hearing it on that day. There is one exception: Cole, Finn and Gwyn are slow, and each of them tells their list two days after the day on which they first heard the news, instead of one day after.

On which day does Ivo first hear the news?

Finish with a final line of the form "ANSWER: <a single integer, the day number on which Ivo first hears the news>"''',
        "answer": "7",
        "answer_type": "int",
    },
    # ---------------------------------------------------------------- kind 8
    {
        "id": "R36",
        "prompt": '''The guild's rent ledger was stolen from the counting-room one afternoon. The steward established the following facts, all of them reliable.

The ledger sat in a chained cradle. Getting it out takes five uninterrupted minutes, and for the whole of those five minutes the thief must be the only person in the room.

Clerk Halvard, in his green coat, was in the room from 2:00 until 2:25; he then went out to the yard and did not come back. Porter Isolde came in at 2:10 and left at 2:22; she returned at 2:40 and left again at 2:46. Scribe Jarrah, who had quarrelled with the steward about wages that morning, was in the room from 2:20 to 2:32. Factor Kelda was there from 2:29 to 2:43. The errand-boy Lorcan was there from 2:42 to 2:53. Mirren the gardener stepped in at 2:36 to hand Kelda a note, noticed the ledger lying untouched in its cradle, and left at 2:37.

At 3:00 the steward walked in and found the cradle empty. Nobody was in the room at any time between 2:00 and 3:00 other than as described.

Who took the ledger?

Finish with a final line of the form "ANSWER: <one name, the person who took the ledger>"''',
        "answer": "Lorcan",
        "answer_type": "str",
    },
    {
        "id": "R37",
        "prompt": '''The hamlet of Orrin has five wells: Abbey, Mill, North, Quarry and Sedge. One morning exactly two of the five wells were tainted. Anyone who drank that day from at least one tainted well fell ill by evening - unless they had eaten bitterroot at breakfast, which protects completely. Nobody fell ill for any other reason.

Bitterroot was served that morning only at the miller's table, and the only people who breakfasted there were Ursa and Zeb; both ate it.

Tobin, who had spent the early morning mending nets, drank from the North and Mill wells and fell ill. Verrin drank from the Mill and Quarry wells and stayed healthy. Ursa drank from the Abbey and Sedge wells and stayed healthy. Wyn, the oldest of them, drank from the Abbey and Quarry wells and fell ill. Zeb drank from the North and Sedge wells and stayed healthy. Each of them drank from no wells other than those mentioned.

Which two wells were tainted?

Finish with a final line of the form "ANSWER: <the names of the two tainted wells, in alphabetical order, comma-separated>"''',
        "answer": "Abbey,North",
        "answer_type": "list",
    },
    {
        "id": "R38",
        "prompt": '''Senna the potter fired her kiln on a market day. In her town, markets are held every Wednesday and every Saturday and on no other days.

She unloaded the kiln three days after the firing (a firing on a Monday, for example, would be unloaded on the Thursday). She meant to take the pots to the guild hall on the day after unloading. But the hall is closed on Sundays and Mondays and open on all other days, so if that day was a closed day she delivered the pots on the next day the hall was open.

The guild's examiner comes to the hall only on Tuesdays, Thursdays and Fridays. He examined her pots on his first visit after the delivery day (never on the delivery day itself).

Senna, who had glazed forty bowls in a new copper green for this firing, remembers that the examination took place more than seven days after the day of the firing.

The results were posted on the third day on which the hall was open after the examination day, not counting the examination day itself.

On which day of the week were the results posted?

Finish with a final line of the form "ANSWER: <one day of the week, written out in full in English>"''',
        "answer": "Tuesday",
        "answer_type": "str",
    },
    {
        "id": "R39",
        "prompt": '''Last night somebody cracked the top shelf in the kiln room at Harrow Pottery. The master has five apprentices - Odo, Perrin, Quenby, Runa and Stellan - and exactly one of them did it, alone. These facts are all reliable.

The kiln room is locked at the 9:00 evening bell and the damage was done after the bell, so the culprit had a key. Keys are held by exactly those apprentices who have completed at least two full years. Odo has completed four years, Perrin two, Quenby one, Runa two and Stellan three.

The chisel bite could only have been made by a left-hander. Perrin is the only right-hander among the five.

The culprit left a floury boot-print. A flour sack burst on the bakery floor at 8:00 that evening; everyone who was in the bakery at any time after 8:00 got flour on their boots, and nobody else did. Odo helped in the bakery from 6:00 to 7:30, Runa and Stellan from 7:00 to 9:00, and Quenby called in from 8:15 to 8:30. Perrin was not there at all.

The ladder was locked in the master's house all night, and without it the top shelf can be reached only by someone tall enough; of the five, only Stellan is too short.

Odo owes the master money, and Quenby was seen outside the kiln room at 8:50.

Who cracked the shelf?

Finish with a final line of the form "ANSWER: <one name, the apprentice who cracked the shelf>"''',
        "answer": "Runa",
        "answer_type": "str",
    },
    {
        "id": "R40",
        "prompt": '''Four barges each carried goods 60 leagues downriver from Tolland to Marrow Quay. A barge covers a fixed number of leagues on every day on which it travels, beginning with the day it sets out, and it arrives on the day on which its total distance covered reaches or passes 60 leagues.

Kite set out on day 1 and covers 7 leagues a day. Heron set out on day 2 and covers 9 leagues a day. Marten set out on day 3 and covers 12 leagues a day. Lark set out on day 4 and covers 20 leagues a day.

Day 5 was a river festival, and no barge moved at all on that day; barges already under way stayed tied up and went on again on day 6.

Kite had the largest crew and Lark was newly painted. Marten carried salt. The saffron was on a barge that reached the quay on a later day than the salt barge, but it was not on the barge that arrived last of the four.

Which barge carried the saffron?

Finish with a final line of the form "ANSWER: <one name, the barge that carried the saffron>"''',
        "answer": "Heron",
        "answer_type": "str",
    },
    # ---------------------------------------------------------------- pilot
    {
        "id": "RP1",
        "prompt": '''Three cups hold beads: the Red cup holds 9, the Green cup holds 4 and the Blue cup holds 12. Carry out these steps in order.

1. Move 3 beads from Red to Green.
2. Move half of Blue's beads into Red.
3. Swap the entire contents of Green and Blue.
4. Move 2 beads from the cup that now holds the most beads to the cup that now holds the fewest (there is no tie at this point).
5. Move one third of Green's beads, rounded down, into Blue.

How many beads does each cup hold at the end?

Finish with a final line of the form "ANSWER: <three integers: the final counts for Red, Green, Blue in that order, comma-separated>"''',
        "answer": "10,6,9",
        "answer_type": "list",
    },
    {
        "id": "RP2",
        "prompt": '''Pickers bring 45 crates of pears into an orchard yard on each of six days, except on day 4, when rain cuts the day's picking to 20 crates. At the end of every day, after that day's crates have come in, carts are loaded from the crates waiting in the yard: each cart takes exactly 32 crates, only completely full carts leave, and as many full carts leave as possible. Crates left over wait in the yard. During the night after each of days 1 to 5, 3 of the waiting crates spoil and are thrown away (if fewer than 3 are waiting, all of them spoil).

How many carts leave in total over the six days, and how many crates are waiting in the yard after the carts have left on day 6?

Finish with a final line of the form "ANSWER: <two integers: the total number of carts, then the number of crates left waiting, comma-separated>"''',
        "answer": "7,8",
        "answer_type": "list",
    },
    {
        "id": "RP3",
        "prompt": '''Five runners - Aldis, Bryn, Cato, Dru and Elke - finished a hill race in places 1 to 5 with no ties; place 1 is the winner, and a smaller place number means finishing ahead.

1. Aldis finished ahead of Cato.
2. Bryn and Dru finished in consecutive places, in one order or the other.
3. Elke finished neither first nor last.
4. Cato finished exactly two places behind Elke.
5. Dru did not win the race.

In what order did the five runners finish?

Finish with a final line of the form "ANSWER: <the five names in finishing order from place 1 to place 5, comma-separated>"''',
        "answer": "Bryn,Dru,Elke,Aldis,Cato",
        "answer_type": "list",
    },
    {
        "id": "RP4",
        "prompt": '''A warehouse adds a check digit to each six-digit serial number, computed as follows.

Step 1: Number the six digits 1 to 6 from left to right. Multiply each digit in an odd-numbered position by 3 and leave each digit in an even-numbered position as it is. Add up the six results.

Step 2: Add 1 to that sum for every digit of the serial number that is greater than 5.

Step 3: Let r be the remainder when the total from step 2 is divided by 10. The check digit is 0 if r is 0; otherwise it is 10 minus r.

What is the check digit for the serial number 480593?

Finish with a final line of the form "ANSWER: <a single digit, the check digit>"''',
        "answer": "3",
        "answer_type": "int",
    },
]

# Metadata for analysis only (not part of the item contract).
KIND_NAMES = {
    1: "constraint/arrangement",
    2: "state tracking",
    3: "quantitative word problem",
    4: "truth-tellers/liars and nested conditionals",
    5: "counting with constraints",
    6: "follow an invented algorithm",
    7: "graph/path reasoning",
    8: "narrative deduction with distractors",
}
KIND = {"R%02d" % i: (i - 1) // 5 + 1 for i in range(1, 41)}
KIND.update({"RP1": 2, "RP2": 3, "RP3": 1, "RP4": 6})

# Author's a-priori difficulty estimate (uncalibrated): M medium, H hard, V very hard.
DIFFICULTY = {
    "R01": "M", "R02": "H", "R03": "H", "R04": "V", "R05": "H",
    "R06": "M", "R07": "H", "R08": "H", "R09": "V", "R10": "H",
    "R11": "M", "R12": "H", "R13": "H", "R14": "V", "R15": "H",
    "R16": "M", "R17": "H", "R18": "H", "R19": "V", "R20": "H",
    "R21": "M", "R22": "H", "R23": "H", "R24": "V", "R25": "H",
    "R26": "M", "R27": "V", "R28": "M", "R29": "H", "R30": "H",
    "R31": "M", "R32": "V", "R33": "H", "R34": "V", "R35": "M",
    "R36": "M", "R37": "M", "R38": "H", "R39": "M", "R40": "H",
    "RP1": "M", "RP2": "M", "RP3": "M", "RP4": "M",
}
