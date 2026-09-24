import { openDB } from "idb";
import type { IDBPDatabase } from "idb";
const DB_NAME = "fileCacheDB";
const STORE_NAME = "files";
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase> | null = null;

function getDB() {
  if (!dbPromise) {
    dbPromise = openDB(DB_NAME, DB_VERSION, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      },
    });
  }
  return dbPromise;
}

export async function saveFile(key: string, blob: Blob): Promise<void> {
  const db = await getDB();
  await db.put(STORE_NAME, blob, key);
}

export async function getFile(key: string): Promise<Blob | undefined> {
  const db = await getDB();
  return db.get(STORE_NAME, key);
}

export async function deleteFile(key: string): Promise<void> {
  const db = await getDB();
  await db.delete(STORE_NAME, key);
}

export async function clearCache(): Promise<void> {
  const db = await getDB();
  await db.clear(STORE_NAME);
}
