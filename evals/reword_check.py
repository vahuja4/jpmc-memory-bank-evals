"""One-off: the 14 retrieval questions from memory_bank_eval_cases.json, each in its original wording and
reworded the way a customer would ask. Loads the 20-fact corpus into a throwaway scope on the engine in
VERTEX_AGENT_ENGINE_ID, runs both wordings, prints per-question hits and totals, deletes the scope, and writes
a JSON result next to this script."""
import json, os, sys, uuid
sys.path.insert(0, "/Users/vishal/google_poc/jpmc-consumer-credit")
from evals.eval_memory_bank import MemoryBankREST, prf, rank_metrics, mean

HERE = os.path.dirname(os.path.abspath(__file__))
cases = json.load(open("/Users/vishal/google_poc/jpmc-consumer-credit/evals/memory_bank_eval_cases.json"))
corpus = cases["retrieval_corpus"]
by_id = {c["id"]: c["fact"] for c in corpus}

REWORDED = {
    "Q01": "my card suddenly stopped working yesterday and nobody told me anything. what happened?",
    "Q02": "overseas payment did not go through....why?",
    "Q03": "i tried to sort out the code thing on the phone the other day but got cut off. did that ever go through?",
    "Q04": "i've got a couple of trips coming up. am i covered for using my card away from home?",
    "Q05": "just checking, is my daughter still able to use her card on my account?",
    "Q06": "i'm still being charged for a gym i cancelled ages ago. is anything being done about that?",
    "Q07": "i moved recently. will my new card come to the right place?",
    "Q08": "if something dodgy happens on my account, how are you going to let me know?",
    "Q09": "i asked for a bit more room on my card a while back. any news?",
    "Q10": "the other card i have, the one my daughter uses, what's going on with that one?",
    "Q11": "there's a big electronics purchase on my statement i'm not sure about. did i ok that?",
    "Q12": "i popped into the branch last week about buying a place. did anyone follow up on that?",
    "Q13": "honestly nothing has worked all week, card, phone wallet, all of it. why?",
    "Q14": "i haven't seen a bill in the post. am i still going to get charged on time?",
}

mb = MemoryBankREST()
scope = f"eval-retrieval-reword-{uuid.uuid4().hex[:6]}"
print(f"engine {mb.engine}\nscope {scope}")
name_to_id = {}
for item in corpus:
    name_to_id[mb.create_fact(item["fact"], scope)] = item["id"]
stored = mb.list_scope(scope)
print(f"stored {len(stored)} of {len(corpus)}")
if len(stored) != len(corpus):
    fact_to_id = {c["fact"]: c["id"] for c in corpus}
    name_to_id = {m["name"]: fact_to_id.get(m.get("fact"), "?") for m in stored}

rows = []
try:
    for q in cases["retrieval_queries"]:
        row = {"id": q["id"], "relevant": q["relevant"], "original": q["query"], "reworded": REWORDED[q["id"]]}
        for key in ("original", "reworded"):
            got = mb.similarity_search(row[key], scope, top_k=5)
            ranked = [name_to_id.get(m["memory"]["name"], "?") for m in got]
            dist = [round(m.get("distance", 0.0), 3) for m in got]
            row[key + "_ranked"] = ranked
            row[key + "_dist"] = dist
            row[key + "@5"] = prf(ranked, q["relevant"], 5)
            row[key + "_rank"] = rank_metrics(ranked, q["relevant"])
        rows.append(row)
        o, r = row["original@5"], row["reworded@5"]
        print(f"\n{q['id']}  relevant {q['relevant']}")
        print(f"  original  hits@5 {o['hits']}/{len(q['relevant'])}  first-hit rank {1/row['original_rank']['reciprocal_rank'] if row['original_rank']['reciprocal_rank'] else '-'}  {row['original_ranked']}  {row['original_dist']}")
        print(f"            {row['original']}")
        print(f"  reworded  hits@5 {r['hits']}/{len(q['relevant'])}  first-hit rank {1/row['reworded_rank']['reciprocal_rank'] if row['reworded_rank']['reciprocal_rank'] else '-'}  {row['reworded_ranked']}  {row['reworded_dist']}")
        print(f"            {row['reworded']}")
finally:
    n = 0
    for m in stored:
        mb.delete(m["name"]); n += 1
    print(f"\ncleanup: deleted {n}")

summary = {}
for key in ("original", "reworded"):
    summary[key] = {
        "recall@5": mean([r[key + "@5"]["recall"] for r in rows]),
        "precision@5": mean([r[key + "@5"]["precision"] for r in rows]),
        "mrr": mean([r[key + "_rank"]["reciprocal_rank"] for r in rows]),
        "top_result_relevant": sum(1 for r in rows if r[key + "_ranked"][:1] and r[key + "_ranked"][0] in r["relevant"]),
        "all_relevant_in_top5": sum(1 for r in rows if r[key + "@5"]["hits"] == len(r["relevant"])),
        "none_in_top5": sum(1 for r in rows if r[key + "@5"]["hits"] == 0),
    }
print("\nSUMMARY", json.dumps(summary, indent=1))
json.dump({"scope": scope, "engine": mb.engine, "rows": rows, "summary": summary},
          open(os.path.join(HERE, "reword_check_result.json"), "w"), indent=1)
print("wrote reword_check_result.json")
