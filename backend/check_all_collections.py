from app.core.firebase import db

# Check both collections
collections = ['competitor_prices', 'competitor_prices_latest']

for coll_name in collections:
    docs = list(db.collection(coll_name).limit(10).stream())
    print(f"\n{coll_name}: {len(docs)} documents")
    
    if docs:
        print("Sample documents:")
        for doc in docs[:3]:
            data = doc.to_dict()
            print(f"  {doc.id}: provider={data.get('provider')}, price={data.get('price_per_day')}, city={data.get('branch_id')}")
