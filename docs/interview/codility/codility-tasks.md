# Codility's own practice tasks

Codility's free practice tasks run in the **real test editor** and are graded by Codility's own hidden tests,
so they are the closest thing to the real test. Each link below opens the task on Codility; the descriptions
here are this guide's own short summaries, not Codility's text. Difficulty labels are Codility's (checked on
11 November 2026). You need a free Codility account to submit.

!!! tip "Order of work"
    1. The [demo test](https://app.codility.com/demo/take-sample-test/).
    2. The three SQL tasks below.
    3. Lessons 1 to 9 (one or two tasks each), then lessons 14 to 16. For a data engineering test this is plenty;
       lessons 10 to 13 and 17 are more mathematical or harder than a data engineering test needs.

## SQL: Exercise 6

**Codility publishes exactly three free SQL tasks**, all in
[Exercise 6](https://app.codility.com/programmers/trainings/6/). (Checked on 11 November 2026: the other eight
exercises and the seventeen lessons hold only programming tasks.) Each of the three lets you choose
**SQL (PostgreSQL)** or **SQL (SQLite)**. Three is not many, so do all three, then use the
[SQL practice set](sql-practice.md) and the sites at the end of this page for volume.

| Task | Level | What it practises | Similar task in this guide |
|---|---|---|---|
| [SqlSum](https://app.codility.com/programmers/trainings/6/sql_sum/) | elementary | The answer format: one aggregate over a table. A warm-up to learn the editor. | [2. Busiest day](sql-practice.md) |
| [SqlEventsDelta](https://app.codility.com/programmers/trainings/6/sql_events_delta/) | easy | Per group, compare the newest row with the one before it, and keep only groups with more than one row. Practise `ROW_NUMBER`/`LAG` per group. | [22. Latest record per customer](sql-practice.md), [23. Month-over-month revenue](sql-practice.md) |
| [SqlWorldCup](https://app.codility.com/programmers/trainings/6/sql_world_cup/) | medium | Turn each match into points for **both** teams, keep teams that played no match with 0, then sort with tie-breakers. | [11. Balances from transfers](sql-practice.md) (one row per side), [Mock 1 task 1](mock-test-1.md) (keep empty groups) |

Hints for these three, without giving the answers away:

* **SqlSum:** check what your query returns on an empty table, if the task allows one.
* **SqlEventsDelta:** "registered more than once" means groups with one row must not appear at all. Number each
  group's rows newest first, then work with rows 1 and 2.
* **SqlWorldCup:** every match involves two teams; `UNION ALL` gives one row per team per match. Start from the
  teams table so that a team with no matches still appears. Read the sort order carefully.

## Python: the lessons

[Codility lessons](https://app.codility.com/programmers/lessons/1-iterations/) each have a short reading (a PDF)
and tasks. The Python practice set in this guide covers the same ideas with original tasks; these are the
Codility tasks to try on the real grader.

| Lesson | Codility tasks (level) | The idea |
|---|---|---|
| 1 Iterations | [BinaryGap](https://app.codility.com/programmers/lessons/1-iterations/binary_gap/) (easy) | Loop over the digits of a number; track the longest run. |
| 2 Arrays | [CyclicRotation](https://app.codility.com/programmers/lessons/2-arrays/cyclic_rotation/) (easy), [OddOccurrencesInArray](https://app.codility.com/programmers/lessons/2-arrays/odd_occurrences_in_array/) (easy) | Index arithmetic with `%`; counting or XOR to find the odd one out. Watch the empty array. |
| 3 Time complexity | [FrogJmp](https://app.codility.com/programmers/lessons/3-time_complexity/frog_jmp/), [PermMissingElem](https://app.codility.com/programmers/lessons/3-time_complexity/perm_missing_elem/), [TapeEquilibrium](https://app.codility.com/programmers/lessons/3-time_complexity/tape_equilibrium/) (all easy) | Replace a loop by a formula; find a missing number from a sum; prefix and suffix totals in one pass. |
| 4 Counting elements | [FrogRiverOne](https://app.codility.com/programmers/lessons/4-counting_elements/frog_river_one/), [PermCheck](https://app.codility.com/programmers/lessons/4-counting_elements/perm_check/) (easy), [MaxCounters](https://app.codility.com/programmers/lessons/4-counting_elements/max_counters/), [MissingInteger](https://app.codility.com/programmers/lessons/4-counting_elements/missing_integer/) (medium) | Sets and counters instead of nested loops. MaxCounters is the classic "lazy update" trap: O(N·M) is too slow. |
| 5 Prefix sums | [PassingCars](https://app.codility.com/programmers/lessons/5-prefix_sums/passing_cars/) (easy), [CountDiv](https://app.codility.com/programmers/lessons/5-prefix_sums/count_div/), [GenomicRangeQuery](https://app.codility.com/programmers/lessons/5-prefix_sums/genomic_range_query/), [MinAvgTwoSlice](https://app.codility.com/programmers/lessons/5-prefix_sums/min_avg_two_slice/) (medium) | Answer many range questions fast with running totals; a counting formula instead of a loop. |
| 6 Sorting | [Distinct](https://app.codility.com/programmers/lessons/6-sorting/distinct/), [MaxProductOfThree](https://app.codility.com/programmers/lessons/6-sorting/max_product_of_three/), [Triangle](https://app.codility.com/programmers/lessons/6-sorting/triangle/) (easy), [NumberOfDiscIntersections](https://app.codility.com/programmers/lessons/6-sorting/number_of_disc_intersections/) (medium) | Sort first, then one pass. Negative numbers matter in the product task. Intervals and sweeping, like Mock 1's Python task. |
| 7 Stacks and queues | [Brackets](https://app.codility.com/programmers/lessons/7-stacks_and_queues/brackets/), [Fish](https://app.codility.com/programmers/lessons/7-stacks_and_queues/fish/), [Nesting](https://app.codility.com/programmers/lessons/7-stacks_and_queues/nesting/), [StoneWall](https://app.codility.com/programmers/lessons/7-stacks_and_queues/stone_wall/) (all easy) | A list used as a stack. Very common in tests. |
| 8 Leader | [Dominator](https://app.codility.com/programmers/lessons/8-leader/dominator/), [EquiLeader](https://app.codility.com/programmers/lessons/8-leader/equi_leader/) (easy) | The value that fills more than half of an array; counting with a `Counter`. |
| 9 Maximum slice | [MaxProfit](https://app.codility.com/programmers/lessons/9-maximum_slice_problem/max_profit/), [MaxSliceSum](https://app.codility.com/programmers/lessons/9-maximum_slice_problem/max_slice_sum/) (easy), [MaxDoubleSliceSum](https://app.codility.com/programmers/lessons/9-maximum_slice_problem/max_double_slice_sum/) (medium) | Best run of consecutive values in one pass (Kadane's method). |
| 10 Prime and composite numbers | [CountFactors](https://app.codility.com/programmers/lessons/10-prime_and_composite_numbers/count_factors/), [MinPerimeterRectangle](https://app.codility.com/programmers/lessons/10-prime_and_composite_numbers/min_perimeter_rectangle/) (easy), [Flags](https://app.codility.com/programmers/lessons/10-prime_and_composite_numbers/flags/), [Peaks](https://app.codility.com/programmers/lessons/10-prime_and_composite_numbers/peaks/) (medium) | Loop only up to the square root. |
| 11 Sieve of Eratosthenes | [CountNonDivisible](https://app.codility.com/programmers/lessons/11-sieve_of_eratosthenes/count_non_divisible/), [CountSemiprimes](https://app.codility.com/programmers/lessons/11-sieve_of_eratosthenes/count_semiprimes/) (medium) | Precompute once, answer many queries. |
| 12 Euclidean algorithm | [ChocolatesByNumbers](https://app.codility.com/programmers/lessons/12-euclidean_algorithm/chocolates_by_numbers/) (easy), [CommonPrimeDivisors](https://app.codility.com/programmers/lessons/12-euclidean_algorithm/common_prime_divisors/) (medium) | Greatest common divisor (`math.gcd`). |
| 13 Fibonacci numbers | [FibFrog](https://app.codility.com/programmers/lessons/13-fibonacci_numbers/fib_frog/), [Ladder](https://app.codility.com/programmers/lessons/13-fibonacci_numbers/ladder/) (medium) | Build values bottom-up; breadth-first search. |
| 14 Binary search | [MinMaxDivision](https://app.codility.com/programmers/lessons/14-binary_search_algorithm/min_max_division/), [NailingPlanks](https://app.codility.com/programmers/lessons/14-binary_search_algorithm/nailing_planks/) (medium) | Binary search on the **answer**: "can it be done with limit X?" |
| 15 Caterpillar method | [AbsDistinct](https://app.codility.com/programmers/lessons/15-caterpillar_method/abs_distinct/), [CountDistinctSlices](https://app.codility.com/programmers/lessons/15-caterpillar_method/count_distinct_slices/), [CountTriangles](https://app.codility.com/programmers/lessons/15-caterpillar_method/count_triangles/) (easy), [MinAbsSumOfTwo](https://app.codility.com/programmers/lessons/15-caterpillar_method/min_abs_sum_of_two/) (medium) | Two pointers / sliding window. |
| 16 Greedy algorithms | [MaxNonoverlappingSegments](https://app.codility.com/programmers/lessons/16-greedy_algorithms/max_nonoverlapping_segments/), [TieRopes](https://app.codility.com/programmers/lessons/16-greedy_algorithms/tie_ropes/) (easy) | Take the best choice now; sort by end time. |
| 17 Dynamic programming | [NumberSolitaire](https://app.codility.com/programmers/lessons/17-dynamic_programming/number_solitaire/) (medium), [MinAbsSum](https://app.codility.com/programmers/lessons/17-dynamic_programming/min_abs_sum/) (hard) | Best score so far for each position. |

## Python: the other exercises

| Exercise | Tasks worth doing (level) | Why |
|---|---|---|
| [5. Coding skills](https://app.codility.com/programmers/trainings/5/) | [ParkingBill](https://app.codility.com/programmers/trainings/5/parking_bill/) (elementary), [ThreeLetters](https://app.codility.com/programmers/trainings/5/three_letters/) (medium) | Parsing time strings and following business rules exactly: close to data engineering work. |
| [4. Algorithmic skills](https://app.codility.com/programmers/trainings/4/) | [FirstUnique](https://app.codility.com/programmers/trainings/4/first_unique/), [StrSymmetryPoint](https://app.codility.com/programmers/trainings/4/str_symmetry_point/) (easy), [ArrayInversionCount](https://app.codility.com/programmers/trainings/4/array_inversion_count/) (medium) | Counting with a dict; a string task; an O(N log N) count. |
| [7. Data Structures](https://app.codility.com/programmers/trainings/7/) | [ArrListLen](https://app.codility.com/programmers/trainings/7/arr_list_len/) (easy), [CountBoundedSlices](https://app.codility.com/programmers/trainings/7/count_bounded_slices/) (medium) | Following links stored in an array; a sliding window with two queues. |

## Other places to practise SQL

Each page below was opened on 11 November 2026 to check what it offers and which database its editor runs.
Codility's practice SQL tasks offer PostgreSQL or SQLite (check what your own test offers): on a site with another database, functions for dates and
text differ (see the table in the [test-day plan](test-day-plan.md#which-sql-dialect)).

| Site | Database | What it has |
|---|---|---|
| [PostgreSQL Exercises](https://pgexercises.com/) | PostgreSQL | Free exercises on one small dataset, grouped into basic queries, joins and subqueries, changing data, aggregates (including window functions), dates, strings and recursive queries. The closest match to Codility's PostgreSQL option. |
| [DataLemur SQL questions](https://datalemur.com/questions) | PostgreSQL 14 by default (MySQL also offered) | Interview-style questions with an online editor, easy to hard. Some questions need a paid account. For example, [Histogram of Tweets](https://datalemur.com/questions/sql-histogram-tweets) is free and practises the same "group, then count the groups" idea as task 7 of the practice set. |
| [HackerRank SQL](https://www.hackerrank.com/domains/sql) | MySQL (default), Oracle, SQL Server or DB2; no PostgreSQL or SQLite | A long list of graded SQL challenges, easy to hard. Good for volume; expect to adjust date and text functions. |
| [SQLZoo](https://sqlzoo.net/wiki/SQL_Tutorial) | a choice of engines | Step-by-step tutorials with small exercises, including joins, `NULL`, self joins and window functions. Good for filling a gap quickly. |
| [SQLite Fiddle](https://sqlite.org/fiddle/) | SQLite | Not a question site: an SQLite that runs in your browser, handy for trying the tasks in this guide with no install. |

LeetCode also has many SQL questions; it isn't listed here because its page couldn't be checked when this list
was made.
