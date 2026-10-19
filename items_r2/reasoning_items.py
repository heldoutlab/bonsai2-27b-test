"""Round-2 (harder) multi-step reasoning items R01-R30 plus calibration items RP1-RP6.

Written from scratch for the bonsai2 pre-registered comparison; never published.
Every key is recomputed by brute force / simulation in reasoning_solvers.py.
The calibration items RP1-RP6 are deliberately the same style and difficulty as
the test items (one per kind).

answer_type:
  int  - a single integer
  str  - a single word / token, compared case-insensitively after stripping
  list - comma-separated values in the order the prompt specifies
"""

ITEMS = [
    # ---------------------------------------------------------------- kind 1
    {
        "id": "R01",
        "prompt": '''A string made of the letters X, Y and Z is rewritten one step at a time using five rules, listed in priority order:

Rule 1: XX becomes YZ
Rule 2: ZYZ becomes XYY
Rule 3: ZZZ becomes X
Rule 4: YZ becomes ZX
Rule 5: XY becomes ZZ

Each step works like this. Find the lowest-numbered rule whose left-hand side occurs somewhere in the current string as a block of adjacent letters; only that rule is used in this step. Steps are counted 1, 2, 3 and so on. On an odd-numbered step, replace the leftmost occurrence of that rule's left-hand side with its right-hand side; on an even-numbered step, replace the rightmost occurrence instead. (Occurrences may overlap; "rightmost" means the occurrence that starts furthest to the right. If there is only one occurrence, it is the one replaced.) Exactly one occurrence is replaced per step, and the next step starts again by checking Rule 1 first. The process stops when no rule's left-hand side occurs anywhere in the string.

The starting string is ZXYYZXXYYZY.

What is the string when the process stops?

Finish with a final line of the form "ANSWER: <the final string, capital letters written together with no spaces or commas>"''',
        "answer": "XZYYY",
        "answer_type": "str",
    },
    {
        "id": "R02",
        "prompt": '''A toy machine has five registers named A, B, C, D and E. They start with A = 5, B = 11, C = 1, D = 0 and E = 30. Register values may become negative. The machine executes the numbered lines below one after another, starting at line 1 and continuing to the next line unless a line tells it to jump. Every line uses the registers' current values.

1. Add A to D.
2. If D is odd, add 3 to A; otherwise subtract 1 from A.
3. Multiply C by 2.
4. If C is greater than 25, subtract 23 from C.
5. Subtract C from E.
6. If E is less than 10, add 25 to E and add 1 to D.
7. Subtract 1 from B.
8. If B is greater than 4, jump to line 1.
9. If D is divisible by 9, jump to line 12.
10. Add C to D, and then swap the values of A and E.
11. Add 1 to C, and then jump to line 9.
12. Stop.

What values do registers A, D and E hold when the machine stops?

Finish with a final line of the form "ANSWER: <three integers: the final values of A, D, E in that order, comma-separated>"''',
        "answer": "10,135,6",
        "answer_type": "list",
    },
    {
        "id": "R03",
        "prompt": '''Ysolde and Brannoch play a game with a face-down deck of 24 number cards. From the top of the deck downwards the cards are:

4, 7, 3, 4, 9, 2, 6, 5, 8, 1, 6, 3, 2, 9, 5, 4, 7, 7, 1, 8, 3, 6, 2, 5.

Both players start with 0 points. A row of face-up cards on the table starts empty. Ysolde takes the first turn.

On a turn the player draws the top card of the deck and places it at the right-hand end of the row. Then the conditions (a), (b), (c) below are checked in that order and only the first one that holds is applied (if none holds, nothing more happens):

(a) The row now contains at least two cards and the new card shows the same number as the card at the left-hand end of the row. The player removes the whole row and scores 1 point for each card removed.
(b) The numbers on all the cards now in the row, including the new card, add up to a multiple of 5. The player removes the new card and also, if there is one, the card immediately to its left, and scores the sum of the numbers on the removed cards.
(c) The row now contains at least two cards and the new card's number differs by exactly 1 from the number on the card immediately to its left. The player scores 2 points, no card is removed, and the same player takes the next turn.

After a turn the other player takes the next turn, except after case (c). Removed cards are out of the game. The game ends as soon as the deck is empty.

What are the final scores, and how many cards are left in the row?

Finish with a final line of the form "ANSWER: <three integers: Ysolde's points, Brannoch's points, number of cards left in the row, comma-separated>"''',
        "answer": "25,36,3",
        "answer_type": "list",
    },
    {
        "id": "R04",
        "prompt": '''Two tokens, Garnet and Teal, move clockwise round a circular track of 14 squares numbered 0 to 13 (after square 13 comes square 0). Garnet starts on square 0 and Teal on square 7, and each token's owner starts with 4 coins. The tokens move alternately, Garnet first, using this fixed list of 18 rolls in order (Garnet uses the 1st, Teal the 2nd, Garnet the 3rd, and so on):

5, 4, 6, 3, 2, 6, 5, 1, 4, 6, 3, 5, 2, 4, 6, 3, 1, 5.

Each turn has three stages, in this order:

Stage 1. Move the token forward by the roll. If this move takes it beyond square 13, so that it passes or lands on square 0, its owner gains 5 coins.
Stage 2. Look at the square where the token landed in stage 1.
- Square 3, 8 or 11 (a slide): the token moves back 2 squares. The square it slides to has no stage-2 effect.
- Square 5 or 10 (a toll): its owner loses 3 coins, or all of their coins if they have fewer than 3.
- Square 2, 6 or 12 (a prize): its owner gains as many coins as the roll just used.
- Any other square: nothing happens.
Stage 3. If the token now stands on the same square as the other token, its owner takes half of the other owner's coins (half rounded down), and then the other token is moved forward 1 square. No stage-1, stage-2 or stage-3 effects apply to that 1-square move.

After all 18 rolls have been used, where is each token and how many coins does each owner have?

Finish with a final line of the form "ANSWER: <four integers: Garnet's square, Garnet's coins, Teal's square, Teal's coins, comma-separated>"''',
        "answer": "2,14,9,13",
        "answer_type": "list",
    },
    {
        "id": "R05",
        "prompt": '''A strip has ten lamps in a row, numbered 1 to 10 from left to right. Each lamp is in state 0, 1 or 2. The starting states of lamps 1 to 10, in order, are:

1 0 2 0 1 2 0 0 2 1.

The strip is updated in rounds. In a round every lamp gets a new state, and all the new states are worked out from the states at the start of that round (all lamps change at the same moment). For a lamp whose current state is s, let n be the sum of the current states of its left-hand neighbour and its right-hand neighbour. Lamp 1 has no left-hand neighbour and lamp 10 has no right-hand neighbour; a missing neighbour counts as 0. The lamp's new state is:

- if n = 0: s (no change);
- if n = 1: s + 1, except that a lamp in state 2 goes to state 0;
- if n = 2: 2 if s is 0, and 0 if s is 1 or 2;
- if n = 3: 1, whatever s is;
- if n = 4: s - 1, except that a lamp in state 0 goes to state 2.

What are the states of the ten lamps after six rounds?

Finish with a final line of the form "ANSWER: <ten digits, the states of lamps 1 to 10 in order, written together with no spaces or commas>"''',
        "answer": "1222110110",
        "answer_type": "str",
    },
    # ---------------------------------------------------------------- kind 2
    {
        "id": "R06",
        "prompt": '''A signal mast at Dunmarrow shows a column of exactly 8 flags, read from the top flag down to the bottom flag. Each flag is red, white or blue, and any colour may be used any number of times (including not at all) as long as the rules are respected. Two flags are "next to each other" when one hangs directly below the other. A signal is valid when all four of these rules hold:

1. No two red flags are next to each other.
2. The number of blue flags in the signal is even (zero counts as even).
3. Nowhere in the column do three consecutive flags read white, blue, white from top to bottom.
4. The top flag is not blue.

Two signals are different if they differ in the colour of at least one of the eight positions. How many different valid signals are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of valid signals>"''',
        "answer": "755",
        "answer_type": "int",
    },
    {
        "id": "R07",
        "prompt": '''Seven different books are to stand in a single row on a shelf: three by Harrowgate (an atlas, a herbal and a memoir), two by Ilves (a primer and a songbook) and two by Jorund (a diary and a lexicon). Every book is distinguishable from every other. An arrangement is acceptable when all three of these rules hold:

1. No two books by the same author stand next to each other.
2. Harrowgate's atlas is not at either end of the row.
3. Jorund's diary stands somewhere to the left of Harrowgate's atlas (not necessarily next to it).

Two arrangements are different if at least one of the seven positions, read from left to right, holds a different book. How many different acceptable arrangements are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of acceptable arrangements>"''',
        "answer": "296",
        "answer_type": "int",
    },
    {
        "id": "R08",
        "prompt": '''A quartermaster hands out exactly 11 identical ration tokens among five crews named Vole, Wren, Xebec, Yarrow and Zinc. All 11 tokens must be handed out. A crew may receive no tokens at all, and no crew may receive more than 4 tokens. In addition, all three of these rules must hold:

1. Vole receives strictly more tokens than Wren.
2. Xebec receives an even number of tokens (0 counts as even).
3. Yarrow and Zinc receive different numbers of tokens.

Two ways of handing out the tokens are different if at least one crew receives a different number of tokens. How many different ways are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of ways>"''',
        "answer": "72",
        "answer_type": "int",
    },
    {
        "id": "R09",
        "prompt": '''A lodge has eight rooms labelled A, B, C, D, E, F, G and H. There are exactly eleven doors, each joining two rooms; the pairs of rooms joined by a door are:

A-B, B-C, C-D, D-E, E-F, F-G, G-H, A-D, B-F, C-H, E-H

Each room is to be painted in one of three colours: red, ochre or green. A painting scheme is allowed when both of these rules hold:

1. Two rooms joined by a door never have the same colour.
2. Exactly three of the eight rooms are red.

Ochre and green may each be used for any number of rooms, including none. Two schemes are different if at least one room gets a different colour. How many different allowed painting schemes are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of allowed schemes>"''',
        "answer": "44",
        "answer_type": "int",
    },
    {
        "id": "R10",
        "prompt": '''A courtyard is paved as a grid of 6 rows and 6 columns of squares. Rows are numbered 1 to 6 from north to south and columns are numbered 1 to 6 from west to east; (r, c) means the square in row r and column c. Six identical lanterns are to be placed on six different squares so that all three of these rules hold:

1. Every row contains exactly one lantern and every column contains exactly one lantern.
2. No lantern stands on a cracked square. The cracked squares are: (1, 3), (2, 5), (3, 1), (3, 2), (3, 5), (4, 2), (4, 3), (6, 4).
3. No two lanterns stand on squares that touch at a corner. In other words, if two lanterns are in rows whose numbers differ by exactly 1, their column numbers must not differ by exactly 1.

Two placements are different if the sets of six squares used are different. How many different placements are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of placements>"''',
        "answer": "19",
        "answer_type": "int",
    },
    # ---------------------------------------------------------------- kind 3
    {
        "id": "R11",
        "prompt": '''Seven lighthouse keepers - Aldric, Bettony, Caius, Dorrit, Esme, Fenwick and Gilda - each live in one of the seven cottages that stand in a single row on Skerrow Head. The cottages are numbered 1 to 7 from west to east, one keeper per cottage. Two cottages are "adjacent" when their numbers differ by exactly 1. "West of" means in a lower-numbered cottage and "east of" means in a higher-numbered cottage. In an "if ... then ..." clue, nothing is claimed when the "if" part is false.

1. Exactly two cottages stand between Esme's cottage and Aldric's cottage.
2. Exactly one of these two statements is true: "Dorrit lives in cottage 3"; "Dorrit's cottage is adjacent to Fenwick's".
3. Exactly two of the four keepers Aldric, Caius, Esme and Gilda live in even-numbered cottages.
4. Caius lives somewhere west of Dorrit.
5. Exactly one of Dorrit, Fenwick and Gilda lives in a cottage numbered lower than Aldric's.
6. If Caius lives west of Aldric, then Fenwick lives east of Dorrit.
7. Esme's cottage is adjacent to neither Dorrit's nor Fenwick's.
8. Fenwick does not live in cottage 1, cottage 2 or cottage 7.
9. Gilda's cottage is adjacent to exactly one of these two cottages: Caius's, Bettony's.
10. If Esme lives in cottage 1, then Gilda does not live in cottage 2.
11. If Gilda lives in an odd-numbered cottage, then Bettony also lives in an odd-numbered cottage.

Who lives in each cottage?

Finish with a final line of the form "ANSWER: <the seven names in cottage order from cottage 1 to cottage 7, comma-separated>"''',
        "answer": "Esme,Caius,Gilda,Aldric,Dorrit,Fenwick,Bettony",
        "answer_type": "list",
    },
    {
        "id": "R12",
        "prompt": '''Eight guests - Halvard, Isaura, Jocasta, Kell, Lysander, Mirren, Njal and Odalys - sit at a round table with eight seats numbered 1 to 8 going clockwise, one guest per seat. Seat 8 is next to seat 1. Two guests are "adjacent" when they are in neighbouring seats. Two guests sit "directly opposite" each other when their seat numbers differ by exactly 4. In an "if ... then ..." clue, nothing is claimed when the "if" part is false.

1. Exactly two of the four guests Isaura, Jocasta, Mirren and Odalys have a seat number greater than 4.
2. If Kell is adjacent to Mirren, then Lysander is adjacent to Njal.
3. Mirren is in neither seat 4 nor seat 6.
4. Exactly one of the three guests Isaura, Kell and Odalys is adjacent to Lysander.
5. Jocasta is in an even-numbered seat.
6. Kell's seat number is higher than Mirren's and lower than Isaura's.
7. If Njal is in an odd-numbered seat, then Mirren is in an even-numbered seat.
8. Halvard sits directly opposite Isaura.
9. Odalys is not adjacent to Halvard.
10. Njal is adjacent to Jocasta.
11. If Halvard is adjacent to Jocasta, then Kell is in an odd-numbered seat.

Who sits in each seat?

Finish with a final line of the form "ANSWER: <the eight names in seat order from seat 1 to seat 8, comma-separated>"''',
        "answer": "Halvard,Mirren,Kell,Odalys,Isaura,Lysander,Njal,Jocasta",
        "answer_type": "list",
    },
    {
        "id": "R13",
        "prompt": '''Six musicians - Pernille, Quentin, Rasmus, Sunniva, Torvald and Ursa - each give one solo recital next week. The six recitals are on six different days, Monday to Saturday, one per day. Each musician plays a different one of these instruments: bassoon, cittern, dulcimer, flute, harp, oboe. "The harp recital" means the recital given by the musician who plays the harp, and similarly for the other instruments. Monday is the earliest day of the week and Saturday the latest. In an "if ... then ..." clue, nothing is claimed when the "if" part is false.

1. Pernille plays neither the bassoon nor the cittern.
2. If Pernille performs before Thursday, then the flute recital is before Wednesday.
3. Exactly one of these two statements is true: "Torvald plays the harp"; "Torvald performs on Thursday".
4. Rasmus does not perform on Wednesday, Thursday or Saturday.
5. Quentin performs later in the week than the bassoon player.
6. Exactly two days lie between the day of the flute recital and the day of the cittern recital.
7. Sunniva performs on the day immediately after the oboe recital.
8. Quentin plays none of these three instruments: bassoon, flute, oboe.
9. The harp recital is on the day immediately before Pernille's recital.
10. Torvald performs earlier in the week than the oboe player.
11. Rasmus performs earlier in the week than Sunniva.
12. Exactly one of the bassoon, dulcimer and harp recitals falls on a Monday, Wednesday or Friday.

Which instrument is played on each day?

Finish with a final line of the form "ANSWER: <the six instruments in day order from Monday to Saturday, comma-separated>"''',
        "answer": "flute,harp,oboe,cittern,bassoon,dulcimer",
        "answer_type": "list",
    },
    {
        "id": "R14",
        "prompt": '''Seven members of a rowing club - Vesna, Wystan, Xanthe, Yorick, Zelda, Ambrose and Briar - each draw one token from a bag that holds nine tokens numbered 1 to 9. No token is drawn twice, so the seven members hold seven different numbers and two of the nine numbers are held by nobody. In an "if ... then ..." clue, nothing is claimed when the "if" part is false.

1. If Vesna's number is greater than Yorick's, then Briar's number is odd.
2. Exactly one of these two statements is true: "Wystan's number is greater than Ambrose's"; "Briar's number is greater than Vesna's".
3. Briar's number is not a multiple of 3.
4. Exactly three of the seven members hold even numbers.
5. Exactly two of the four members Wystan, Yorick, Ambrose and Briar hold numbers less than 3.
6. The number 8 is not held by Vesna, Xanthe or Zelda.
7. The largest of the seven numbers is held by Xanthe or by Zelda.
8. Ambrose's number is odd.
9. Exactly one of these two statements is true: "Vesna's number is a multiple of 3"; "Zelda's number is a multiple of 3".
10. Zelda's number is greater than Vesna's.
11. Xanthe's number is larger than Zelda's.
12. Vesna's number plus Wystan's number equals twice Yorick's number.

Which number does each member hold?

Finish with a final line of the form "ANSWER: <seven integers: the numbers held by Vesna, Wystan, Xanthe, Yorick, Zelda, Ambrose, Briar in that order, comma-separated>"''',
        "answer": "6,2,9,4,7,1,5",
        "answer_type": "list",
    },
    {
        "id": "R15",
        "prompt": '''Eight crates are loaded onto three trucks called Red, Tan and Violet. The crates and their weights in hundredweight are: anvil 9, barrel 4, cable 6, drum 7, engine 11, fleece 2, girder 8, hawser 3. Every crate goes on exactly one truck, and every truck carries at least two crates. A truck's "total load" is the sum of the weights of the crates on it. In an "if ... then ..." clue, nothing is claimed when the "if" part is false.

1. Exactly one of these two statements is true: "the drum and the girder are on the same truck"; "the drum and the anvil are on the same truck".
2. The drum is not on the Tan truck.
3. The truck carrying the cable has a total load of less than 15.
4. The fleece and the cable are on different trucks.
5. The barrel is not on the Red truck.
6. The engine is not on the Red truck.
7. The Red truck's total load is an even number.
8. The girder shares its truck with exactly one other crate.
9. If the cable is on the Tan truck, then the girder is on the Red truck.
10. The fleece and the hawser are on different trucks.
11. The Violet truck carries exactly two crates.

Which truck carries each crate?

Finish with a final line of the form "ANSWER: <eight letters, each R, T or V, giving the trucks of the anvil, barrel, cable, drum, engine, fleece, girder, hawser in that order, comma-separated>"''',
        "answer": "R,T,V,R,T,R,V,T",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 4
    {
        "id": "R16",
        "prompt": '''Ten islands - Arrow, Brine, Cask, Dune, Ember, Flint, Gull, Haven, Islet and Jetty - are linked by the seventeen ferry services listed below. Every service runs in one direction only. A line "X to Y: first m, every p, takes d" means that boats leave X for Y at minute m and then every p minutes after that (at minutes m, m + p, m + 2p, and so on), and that each boat reaches Y exactly d minutes after it leaves X.

Arrow to Brine: first 22, every 45, takes 17
Arrow to Dune: first 12, every 25, takes 14
Arrow to Gull: first 32, every 40, takes 21
Brine to Haven: first 11, every 40, takes 28
Cask to Brine: first 13, every 40, takes 12
Cask to Dune: first 10, every 20, takes 19
Cask to Haven: first 33, every 45, takes 28
Cask to Jetty: first 17, every 60, takes 14
Dune to Flint: first 23, every 40, takes 19
Dune to Gull: first 11, every 35, takes 26
Dune to Haven: first 19, every 20, takes 14
Flint to Ember: first 15, every 60, takes 23
Gull to Ember: first 14, every 40, takes 21
Gull to Haven: first 39, every 50, takes 34
Gull to Jetty: first 39, every 50, takes 23
Haven to Islet: first 18, every 35, takes 12
Islet to Jetty: first 16, every 25, takes 31

Tamsel is standing on Arrow at minute 0 and wants to reach Jetty. At an island she may board any boat that leaves at or after the minute she arrives there (changing boats takes no time, and she may wait as long as she likes). She can travel only by these ferries.

What is the earliest minute at which she can arrive on Jetty?

Finish with a final line of the form "ANSWER: <a single integer, the minute of her earliest possible arrival on Jetty>"''',
        "answer": "97",
        "answer_type": "int",
    },
    {
        "id": "R17",
        "prompt": '''Eleven depots are labelled A, B, C, D, E, F, G, H, J, K and L (there is no depot I). They are joined by nineteen two-way roads. The roads and their lengths in km are:

A-J 17; B-F 7; B-G 10; B-J 10; B-K 7; C-G 17; C-H 12; C-J 15; C-K 17; C-L 17; D-H 7; D-K 10; E-H 8; F-G 19; F-J 19; F-K 13; G-K 10; H-L 18; J-K 7.

An electric van leaves depot A with a full battery and must reach depot L. A full battery is enough for exactly 30 km. Only depots B, C and G have chargers: every time the van is at one of those three depots its battery is refilled to full at once, at no cost. The van may drive along a road only if the road is no longer than the distance its battery can still cover at that moment (arriving with exactly 0 km left is allowed). It may pass through any depot, and use any road, more than once.

What is the smallest total distance the van can drive to get from depot A to depot L?

Finish with a final line of the form "ANSWER: <a single integer, the smallest possible total distance in km>"''',
        "answer": "68",
        "answer_type": "int",
    },
    {
        "id": "R18",
        "prompt": '''Twelve villages are labelled A, B, C, D, E, F, G, H, J, K, L and M (there is no village I). They are joined by twenty two-way paths, all of different lengths. The paths and their lengths in km are:

A-F 20; A-H 23; A-K 30; B-D 24; C-E 14; C-J 10; C-K 8; D-F 37; D-H 33; D-M 17; E-G 4; F-G 16; F-J 11; G-K 25; G-L 22; G-M 27; H-J 5; H-L 39; K-L 35; L-M 29.

A surveyor starts at village A, which counts as the first village she has visited. She then applies the following rule again and again, and stops at the moment she first enters the twelfth village.

- Look at the paths that lead from the village she is in now to villages she has not yet visited. If there is at least one such path, she walks along one of them: normally the shortest of them, but if the number of villages visited so far (counting A and the village she is in now) is a multiple of 3, the longest of them instead. The village she reaches now counts as visited.
- If there is no such path, she walks back along the path by which she first entered the village she is in now, and applies the rule again from the village she returns to.

Walking back counts towards the distance walked but does not change the number of villages visited.

What total distance does she walk, and which village does she visit last?

Finish with a final line of the form "ANSWER: <the total distance in km as an integer, then the letter of the last village visited, comma-separated>"''',
        "answer": "358,E",
        "answer_type": "list",
    },
    {
        "id": "R19",
        "prompt": '''Twelve relay huts are labelled A, B, C, D, E, F, G, H, J, K, L and M (there is no hut I). There are 24 possible cable runs, each joining two huts, and all have different costs. The possible runs and their costs in crowns are:

A-B 58; A-K 46; B-C 44; B-E 35; B-G 29; C-D 73; C-E 38; C-J 18; D-E 27; D-G 76; D-J 26; D-K 28; E-F 51; E-J 11; E-K 63; E-M 66; F-H 53; F-J 39; F-L 12; G-J 48; H-K 49; H-L 69; H-M 59; L-M 23.

An engineer considers the 24 runs one at a time in order of increasing cost, starting with the cheapest. She builds the run she is considering unless at least one of these is true at that moment:

(a) its two huts are already joined to each other by cables built so far, either directly or through a chain of other huts;
(b) at least one of its two huts already has two built cables attached to it.

A run that is not built is never considered again.

After all 24 runs have been considered, what is the total cost of the cables built, and into how many separate groups do the twelve huts fall? (Two huts are in the same group when they are joined by built cables directly or through a chain of other huts; a hut with no cable at all would be a group by itself.)

Finish with a final line of the form "ANSWER: <two integers: the total cost of the built cables, then the number of groups, comma-separated>"''',
        "answer": "291,2",
        "answer_type": "list",
    },
    {
        "id": "R20",
        "prompt": '''A boatyard must complete eleven tasks, A to K, with a crew of 7 workers. Each task needs a fixed number of days and a fixed number of workers, and can start only when all of its prerequisite tasks have finished:

A: 6 days, 2 workers, prerequisites none
B: 5 days, 5 workers, prerequisites none
C: 2 days, 5 workers, prerequisites A and B
D: 5 days, 5 workers, prerequisites none
E: 5 days, 4 workers, prerequisites A and C
F: 2 days, 4 workers, prerequisites E
G: 2 days, 2 workers, prerequisites none
H: 7 days, 3 workers, prerequisites A and D
I: 3 days, 5 workers, prerequisites A and E
J: 4 days, 3 workers, prerequisites D and I
K: 4 days, 2 workers, prerequisites H

Once started, a task runs without a break for its number of days and keeps its workers busy for the whole of that time; they become free at the moment it finishes. A worker cannot work on two tasks at once. Time is measured in days from time 0.

The foreman applies the following rule at time 0, and again at every moment when one or more tasks finish (the workers of all tasks finishing at that moment are freed first). He goes through the tasks that have not yet started in alphabetical order. For each one in turn: if all its prerequisites have finished and the number of workers free at that instant is at least the number it needs, it starts immediately (and those workers are no longer free for the tasks after it in the list); otherwise it is skipped until the next time the rule is applied.

At what time does the last task finish, and at what time does task K start?

Finish with a final line of the form "ANSWER: <two integers: the time at which the last task finishes, then the time at which task K starts, comma-separated>"''',
        "answer": "26,19",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 5
    {
        "id": "R21",
        "prompt": '''On the island of Quorrin every islander is exactly one of three kinds. A Steadfast makes only true statements. A Twister makes only false statements. A Drifter who makes two statements always makes one true statement and one false statement, in either order. Six islanders - Brannick, Cosima, Dagny, Evander, Fliss and Gorran - each make two statements, in the order shown. "The six of us" means these six islanders.

Brannick: (1) "Fliss is not a Steadfast." (2) "At least one of Evander and Gorran is a Drifter."
Cosima: (1) "Brannick is a Steadfast and Gorran is a Twister." (2) "At most one of the six of us is a Twister."
Dagny: (1) "At most two of the six of us are Steadfasts." (2) "Fliss is a Drifter."
Evander: (1) "Gorran is a Drifter." (2) "Dagny and Gorran are of the same kind."
Fliss: (1) "Evander is a Twister." (2) "Cosima is a Drifter."
Gorran: (1) "Evander's second statement is true." (2) "Evander and I are of different kinds."

What kind is each islander?

Finish with a final line of the form "ANSWER: <six letters, each S (Steadfast), T (Twister) or D (Drifter), for Brannick, Cosima, Dagny, Evander, Fliss, Gorran in that order, comma-separated>"''',
        "answer": "D,T,S,T,D,T",
        "answer_type": "list",
    },
    {
        "id": "R22",
        "prompt": '''A brass sextant was taken from the harbour office by exactly one of five clerks: Hesketh, Imre, Juno, Kasimir and Leda. Each clerk is exactly one of three kinds. A Verity makes only true statements. A Falsifier makes only false statements. An Alternator's statements strictly alternate between true and false in the order they are made, so of three statements either the first and third are true and the second is false, or the first and third are false and the second is true. Each clerk makes three statements, in the order shown. "The five of us" means these five clerks.

Hesketh: (1) "Leda is a Verity and Kasimir is an Alternator." (2) "At least one of Juno and Kasimir is an Alternator." (3) "Kasimir and Imre are of the same kind."
Imre: (1) "Leda's second statement is true." (2) "The sextant was taken by Hesketh or by Juno." (3) "At most one of the five of us is a Falsifier."
Juno: (1) "Neither Leda nor Imre took the sextant." (2) "Leda and I are of different kinds." (3) "Imre is an Alternator and Leda is an Alternator."
Kasimir: (1) "The person who took the sextant is not a Verity." (2) "The sextant was taken by Imre or by Leda." (3) "Juno is not a Falsifier."
Leda: (1) "Juno took the sextant." (2) "The person who took the sextant is an Alternator." (3) "The sextant was taken by Imre or by Juno."

Who took the sextant, and what kind is each clerk?

Finish with a final line of the form "ANSWER: <six entries, comma-separated: the name of the clerk who took the sextant, then five letters, each V (Verity), F (Falsifier) or A (Alternator), for Hesketh, Imre, Juno, Kasimir, Leda in that order>"''',
        "answer": "Leda,A,F,A,V,F",
        "answer_type": "list",
    },
    {
        "id": "R23",
        "prompt": '''A card carries the nine numbered statements below, which talk about one another. Each statement is either true or false. The assignment of true and false must be consistent: every statement marked true must be correct about the whole assignment, and every statement marked false must be incorrect about it. "These nine statements" always means all nine statements on the card, including the statement that is speaking.

1. The number of true statements among these nine is even.
2. Exactly two of the odd-numbered statements (1, 3, 5, 7, 9) are true.
3. At least two of statements 1, 2, 3 and 4 are true.
4. Statement 3 and statement 5 have the same truth value (both true or both false).
5. Exactly five of these nine statements are true.
6. Statement 9 is false.
7. Statement 1 is false.
8. Statement 7 and statement 9 have the same truth value (both true or both false).
9. Exactly one of statements 4 and 5 is true.

There is exactly one consistent assignment. Which statements are true?

Finish with a final line of the form "ANSWER: <the numbers of the true statements in increasing order, comma-separated>"''',
        "answer": "3,4,5,6,7",
        "answer_type": "list",
    },
    {
        "id": "R24",
        "prompt": '''The Garnet Tower has a whole number of steps, somewhere from 10 to 40 inclusive, so the number of steps has exactly two digits: a tens digit and a units digit. Six wardens - Maelis, Nico, Oswin, Petra, Quillon and Runa - each know the number. Each warden is exactly one of three kinds. A Candid makes only true statements. A Guiler makes only false statements. A Halfling who makes two statements always makes one true statement and one false statement, in either order. Each warden makes two statements, in the order shown. "The six of us" means these six wardens. The number 1 is not a prime number.

Maelis: (1) "I am not a Halfling." (2) "Runa is a Candid."
Nico: (1) "Petra is a Candid." (2) "The number of steps is a prime number."
Oswin: (1) "The number of steps is even." (2) "The number of steps is not a multiple of 5."
Petra: (1) "At most two of the six of us are Candids." (2) "The two digits of the number of steps differ by exactly 1."
Quillon: (1) "The number of steps is a multiple of 3." (2) "Among the six of us there are more Candids than Guilers."
Runa: (1) "The number of steps is less than 12." (2) "Quillon is not a Halfling."

How many steps does the Garnet Tower have?

Finish with a final line of the form "ANSWER: <a single integer, the number of steps>"''',
        "answer": "11",
        "answer_type": "int",
    },
    {
        "id": "R25",
        "prompt": '''Seven villagers each make exactly one statement, speaking one after another in this order: Sable, Tiernan, Ulla, Vance, Wilhelmina, Xavi, Yseult. Each villager is exactly one of three kinds. A Plainspeaker's statement is true. A Deceiver's statement is false. A Contrary's statement is true if the statement made by the villager who speaks immediately before them is false, and false if that statement is true. For this purpose the villager "immediately before" Sable is Yseult, the last speaker. "The seven of us" means these seven villagers.

Sable: "Wilhelmina and I are of different kinds."
Tiernan: "At most two of the seven of us are Contraries."
Ulla: "Xavi and Sable are of the same kind."
Vance: "Tiernan and I are of different kinds."
Wilhelmina: "At least one of Xavi and Vance is a Deceiver."
Xavi: "Vance is a Deceiver and Tiernan is a Deceiver."
Yseult: "Wilhelmina is a Plainspeaker and Vance is a Contrary."

What kind is each villager?

Finish with a final line of the form "ANSWER: <seven letters, each P (Plainspeaker), D (Deceiver) or C (Contrary), for Sable, Tiernan, Ulla, Vance, Wilhelmina, Xavi, Yseult in that order, comma-separated>"''',
        "answer": "P,D,C,D,C,P,C",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- kind 6
    {
        "id": "R26",
        "prompt": '''The year 2027 is not a leap year (February has 28 days), and 1 January 2027 is a Friday. An orchard plans two recurring jobs for 2027.

Pruning is planned for Tuesday 5 January and then every 9 days after that (so 14 January, 23 January, and so on).
Spraying is planned for Monday 11 January and then every 14 days after that.

Planned dates continue in this way up to 31 December 2027. Two rules change what is actually done:

Rule 1. Nobody works on Sundays. A job whose planned date is a Sunday is done on the following day, Monday, instead. This does not shift any later planned dates: they are still counted from the original planned dates.
Rule 2. The orchard is closed for the whole of August. A job whose date, after rule 1 has been applied, falls in August is not done at all and is not made up later.

A "double day" is a date on which pruning and spraying are both actually done. What is the date of the third double day of 2027?

Finish with a final line of the form "ANSWER: <two integers: the day of the month, then the number of the month (January = 1), comma-separated; for example 9 March would be 9,3>"''',
        "answer": "6,9",
        "answer_type": "list",
    },
    {
        "id": "R27",
        "prompt": '''A water tower holds 420 litres at 06:00. Water is drawn from it at these rates: 6 litres per minute from 06:00 to 07:30, 14 litres per minute from 07:30 to 09:00, 9 litres per minute from 09:00 to 11:00, and 17 litres per minute from 11:00 to 12:00. A pump, which is off at 06:00, adds 25 litres per minute while it is on.

Work in whole minutes. At the start of each minute (06:00, 06:01, and so on up to 11:59) the controller first looks at the level at that instant:
- if the pump is off and the level is below 300 litres, the pump is switched on;
- if the pump is on and the level is 800 litres or more, the pump is switched off;
- otherwise the pump is left as it is.
Then, during that minute, the level changes by the pump's 25 litres (if the pump is now on) minus the draw rate for that minute. A draw rate given "from 07:30" applies to the minute that starts at 07:30 and no earlier.

What is the level at 12:00, and for how many minutes in total was the pump on between 06:00 and 12:00?

Finish with a final line of the form "ANSWER: <two integers: the level in litres at 12:00, then the total number of minutes the pump was on, comma-separated>"''',
        "answer": "445,157",
        "answer_type": "list",
    },
    {
        "id": "R28",
        "prompt": '''Tessaly's workshop receives four quarterly electricity bills in one year. The figures for each quarter are:

Quarter 1: 1340 kWh used, 90 days, 120 kWh exported.
Quarter 2: 870 kWh used, 91 days, 900 kWh exported.
Quarter 3: 610 kWh used, 92 days, 1100 kWh exported.
Quarter 4: 1515 kWh used, 92 days, 200 kWh exported.

All money is in pence. Each quarter's bill is worked out in these steps:

1. Energy charge: the first 400 kWh used in the quarter cost 21 pence each, the next 600 kWh cost 17 pence each, and any kWh above 1000 cost 26 pence each.
2. Standing charge: 43 pence for each day of the quarter.
3. Export credit: each kWh exported in the quarter earns 9 pence of credit. The credit available is the credit earned this quarter plus any credit carried over from the previous quarter. The credit used is the whole available credit, except that it may not be more than half of this quarter's energy charge. Available credit that is not used is carried over to the next quarter; anything left after quarter 4 is lost.
4. Subtotal = energy charge + standing charge - credit used.
5. Levy = 5 percent of the subtotal, rounded down to a whole number of pence.
6. Bill = subtotal + levy. Then, in quarters 2, 3 and 4 only, if fewer kWh were used in this quarter than in the previous quarter, 250 pence is taken off the bill.

What is the total of the four bills?

Finish with a final line of the form "ANSWER: <a single integer, the total of the four bills in pence>"''',
        "answer": "86234",
        "answer_type": "int",
    },
    {
        "id": "R29",
        "prompt": '''A barge leaves Marlock Basin at 07:10 and travels up a canal to Pell Wharf. On the way it passes, in this order: reach 1, lock 1, reach 2, lock 2, reach 3, lock 3, reach 4, lock 4, reach 5. The lengths of the reaches and the barge's constant speed on each are: reach 1, 6 km at 8 km/h; reach 2, 4 km at 6 km/h; reach 3, 9 km at 12 km/h; reach 4, 5 km at 10 km/h; reach 5, 7 km at 6 km/h.

Each lock works in cycles. Lock 1 starts a cycle at 07:00 and every 20 minutes after that; lock 2 at 07:10 and every 35 minutes after that; lock 3 at 07:05 and every 25 minutes after that; lock 4 at 07:15 and every 30 minutes after that. The barge goes through a lock on the first cycle that starts at or after the moment the barge is ready at that lock, and it leaves the lock exactly 12 minutes after that cycle starts. Exception: all locks are shut over lunch, so any cycle whose start time is 11:40 or later but before 12:25 does not take place; the other cycle start times are unchanged.

Rest rule: at the end of each of reaches 1 to 4 the skipper works out the engine time, meaning the minutes spent travelling along reaches since leaving Marlock Basin or since the end of the last rest, whichever is later. If the engine time is 80 minutes or more, he moors for a 15-minute rest, the engine time goes back to zero, and only after the rest is the barge ready at the lock. Otherwise the barge is ready at the lock at once. Waiting, resting and passing through locks do not count as engine time.

At what time does the barge arrive at Pell Wharf?

Finish with a final line of the form "ANSWER: <the arrival time on the 24-hour clock as four digits HHMM written together with no colon or spaces, for example 0905>"''',
        "answer": "1407",
        "answer_type": "str",
    },
    {
        "id": "R30",
        "prompt": '''Corvane borrows 4800 crowns from a guild. At the end of every month (month 1, month 2, month 3, and so on) the following three things happen, in this order:

1. Interest is added to the balance: 2 percent of the balance if the balance is 3000 crowns or more at that moment, and 1 percent of the balance otherwise. The interest is rounded down to a whole number of crowns.
2. Corvane makes a payment. The payment due is 450 crowns, except in months whose number is a multiple of 4, when it is only 200 crowns. If the balance (after step 1) is less than or equal to the payment due, she pays exactly the balance, the loan is finished, and nothing further happens.
3. If the loan is not finished and the month number is a multiple of 6, a fee of 25 crowns is added to the balance.

In which month does Corvane make her final payment, and how many crowns is that final payment?

Finish with a final line of the form "ANSWER: <two integers: the number of the month of the final payment, then the amount of the final payment in crowns, comma-separated>"''',
        "answer": "14,348",
        "answer_type": "list",
    },
    # ---------------------------------------------------------------- calibration
    {
        "id": "RP1",
        "prompt": '''A clerk has a queue of numbered tickets and a pile of tickets that starts empty. From front to back, the numbers on the tickets in the queue are:

14, 8, 9, 5, 13, 11, 7, 4, 3, 6, 12, 10.

The clerk repeats the following step until the queue is empty. Take the ticket at the front of the queue; call its number n. If the pile is not empty, call the number on the pile's top ticket t.

- If the pile is empty, or n is greater than t: put the ticket on top of the pile.
- If n is equal to t: throw away both the ticket just taken and the top ticket of the pile.
- If n is less than t: remove the top ticket from the pile and throw it away; write a new ticket carrying the number t - n and add it at the back of the queue; then put the ticket numbered n on top of the pile, without comparing it with whatever is now beneath it.

Only the top ticket of the pile is ever compared, and each step handles exactly one ticket from the front of the queue.

When the queue is empty, which numbers are on the pile?

Finish with a final line of the form "ANSWER: <the numbers on the pile from the bottom ticket to the top ticket, comma-separated>"''',
        "answer": "8,5,3,6,2,1",
        "answer_type": "list",
    },
    {
        "id": "RP2",
        "prompt": '''A floor is a rectangle of 4 rows and 7 columns of unit squares. Rows are numbered 1 to 4 from top to bottom and columns are numbered 1 to 7 from left to right. Two of the squares are occupied by pillars and cannot be covered: (row 2, column 6) and (row 3, column 4).

The remaining 26 squares are to be covered completely with 13 identical planks. Each plank covers exactly two squares that share a side, so it lies either horizontally (two neighbouring squares in the same row) or vertically (two neighbouring squares in the same column). Planks may not overlap, may not cover a pillar square and may not stick out beyond the floor.

Two coverings are different if there is at least one pair of squares that is covered by a single plank in one covering but not in the other. How many different coverings are there?

Finish with a final line of the form "ANSWER: <a single integer, the number of coverings>"''',
        "answer": "83",
        "answer_type": "int",
    },
    {
        "id": "RP3",
        "prompt": '''Six residents - Corvin, Delwyn, Eluned, Fabian, Greta and Hesper - live in a six-storey house, one resident on each floor. The floors are numbered 1 (bottom) to 6 (top). Each resident keeps exactly one pet, which is a cat, a dog or a finch; several residents may keep the same kind of pet, and a kind may be kept by nobody unless a clue says otherwise. "Consecutive floors" are floors whose numbers differ by exactly 1. In an "if ... then ..." clue, nothing is claimed when the "if" part is false.

1. If Eluned keeps a dog, then Greta keeps a dog.
2. Fabian and Corvin keep the same kind of pet.
3. The resident of floor 1 keeps a dog.
4. Delwyn lives on the floor directly above Hesper's.
5. The residents of floor 2 and floor 4 keep the same kind of pet.
6. Corvin lives on neither floor 1 nor floor 3.
7. If Hesper keeps a cat, then Delwyn does not keep a dog.
8. Exactly three of the six residents keep a cat.
9. No two residents living on consecutive floors both keep dogs.
10. Exactly one of these two statements is true: "Fabian lives on floor 6"; "Fabian keeps a dog".
11. Corvin lives on a lower floor than Greta.
12. Delwyn lives on a higher floor than Greta.

Who lives on each floor?

Finish with a final line of the form "ANSWER: <the six names in floor order from floor 1 to floor 6, comma-separated>"''',
        "answer": "Eluned,Corvin,Greta,Hesper,Delwyn,Fabian",
        "answer_type": "list",
    },
    {
        "id": "RP4",
        "prompt": '''Two potters, Wren and Pike, share eleven jobs, A to K. Each job takes a fixed number of whole hours and can start only when all of its prerequisite jobs have finished. Jobs marked "kiln" can be done only by Wren; any other job can be done by either potter.

A: 4 hours, prerequisites none
B: 2 hours, prerequisites none
C: 5 hours, prerequisites none
D: 8 hours, prerequisites A and C, kiln
E: 5 hours, prerequisites none
F: 9 hours, prerequisites B and E, kiln
G: 9 hours, prerequisites C and E, kiln
H: 4 hours, prerequisites A and C, kiln
I: 7 hours, prerequisites C
J: 8 hours, prerequisites B
K: 9 hours, prerequisites I

A potter works on one job at a time and, once started, a job runs without a break; a job is done by one potter alone. Time is measured in hours from time 0. A job is "ready" when it has not been started and all its prerequisites have finished.

Jobs are handed out at time 0 and again at every moment when a job finishes, like this. First, if Wren is idle, she starts the ready job that takes the most hours (if several tie, the one earliest in the alphabet); if no job is ready she stays idle. Then, if Pike is idle, he starts the ready job without a kiln mark that takes the most hours (same tie rule), not counting any job Wren has just started; if there is none he stays idle. An idle potter waits until the next moment a job finishes.

At what time does the last job finish, and how many of the eleven jobs does Pike do?

Finish with a final line of the form "ANSWER: <two integers: the time at which the last job finishes, then the number of jobs done by Pike, comma-separated>"''',
        "answer": "39,5",
        "answer_type": "list",
    },
    {
        "id": "RP5",
        "prompt": '''In the town of Ostrel every citizen is exactly one of three kinds. A Keeper makes only true statements. A Bender makes only false statements. A Flipper's statements strictly alternate between true and false in the order they are made, so of three statements either the first and third are true and the second is false, or the first and third are false and the second is true. Five citizens - Anwen, Bede, Calla, Dov and Edda - each make three statements, in the order shown. "The five of us" means these five citizens.

Anwen: (1) "Bede's first statement is true." (2) "Edda is a Bender and Dov is a Keeper." (3) "Exactly two of the five of us are Flippers."
Bede: (1) "Exactly two of the five of us are Keepers." (2) "At least one of these is the case: Anwen is a Bender; Edda is a Keeper." (3) "At least one of these is the case: Dov is a Keeper; Edda is a Flipper."
Calla: (1) "Among the five of us there are more Flippers than Benders." (2) "Bede is a Bender." (3) "Bede and Edda are of the same kind."
Dov: (1) "Calla is a Keeper and Anwen is a Bender." (2) "Exactly three of the five of us are Keepers." (3) "Edda is a Flipper."
Edda: (1) "Calla and I are of different kinds." (2) "I am not a Flipper." (3) "Dov and I are of different kinds."

What kind is each citizen?

Finish with a final line of the form "ANSWER: <five letters, each K (Keeper), B (Bender) or F (Flipper), for Anwen, Bede, Calla, Dov, Edda in that order, comma-separated>"''',
        "answer": "B,F,B,B,K",
        "answer_type": "list",
    },
    {
        "id": "RP6",
        "prompt": '''A bakery tracks its flour, eggs and loaves over seven days. Before day 1 it has 26 kg of flour, 45 eggs and no loaves. On each day the following four things happen, in this order:

1. Deliveries. Flour delivered on days 1 to 7, in kg: 0, 30, 0, 20, 0, 36, 0. Eggs delivered on days 1 to 7: 40, 40, 20, 20, 40, 60, 80.
2. Baking. One batch uses 4 kg of flour and 10 eggs and makes 12 loaves. The bakery bakes as many whole batches as it can with the flour and eggs it has, but the oven allows at most 5 batches a day on days 1 to 5, at most 7 on day 6 and at most 3 on day 7.
3. Selling. The number of loaves customers want on days 1 to 7 is: 53, 77, 20, 20, 35, 59, 26. Loaves left over from the previous day are sold first, then loaves baked today. The bakery cannot sell more loaves than customers want, nor more than it has.
4. Closing. Any loaves left over from the previous day that are still unsold are thrown away. Unsold loaves baked today are kept, and tomorrow they are the "loaves left over from the previous day".

Flour and eggs never spoil. Over the seven days, how many loaves are sold in total, how many loaves are thrown away in total, and how many eggs are left at the end of day 7?

Finish with a final line of the form "ANSWER: <three integers: total loaves sold, total loaves thrown away, eggs left after day 7, comma-separated>"''',
        "answer": "280,32,65",
        "answer_type": "list",
    },
]

KIND_NAMES = {
    1: "long simulation with interacting rules",
    2: "counting with constraints",
    3: "constraint puzzle (6-8 entities, 11-12 clues)",
    4: "graph / scheduling with a stated greedy rule and a twist",
    5: "truth-tellers, liars and self-reference (three speaker kinds)",
    6: "multi-stage quantitative",
}
KIND = {"R%02d" % i: (i - 1) // 5 + 1 for i in range(1, 31)}
KIND.update({"RP%d" % i: i for i in range(1, 7)})
