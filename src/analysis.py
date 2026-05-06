# from collections import Counter


# all_rolls = [
#     (a, b, c) for a in range(6, 0, -1) for b in range(a, 0, -1) for c in range(b, 0, -1)
# ]

# sorted_rolls = sorted(all_rolls, key=classify)

# roll_index = {roll: i for i, roll in enumerate(sorted_rolls)}


# results = [play_turn(GreedyAllIn()) for _ in range(10000)]
# results2 = [play_turn(ThresholdStrategy(threshold=(1, 6))) for _ in range(10000)]

# print(sum(r["final"] == (1, 1, 1) for r in results))
# print(sum(r["rolls_used"] for r in results) / len(results))
# print(Counter(r["rank"] for r in results))

# print(sum(r["final"] == (1, 1, 1) for r in results2))
# print(sum(r["rolls_used"] for r in results2) / len(results2))
# print(Counter(r["rank"] for r in results2))
