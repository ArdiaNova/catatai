import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])
row = sb.table("owners").insert({"channel": "test", "external_id": "db-test", "shop_name": "tes"}).execute().data[0]
print("insert ok:", row["id"])
print("read ok:", len(sb.table("owners").select("*").eq("channel", "test").execute().data), "baris")
sb.table("owners").delete().eq("id", row["id"]).execute()
print("cleanup ok")
