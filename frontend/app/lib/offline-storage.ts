import { ChatMessage, SavedGuidanceItem, SupportedLanguage } from "../types";

const DB_NAME = "farmsaathi_offline_store";
const DB_VERSION = 1;
const STORE_CONVERSATION = "conversations";
const STORE_SAVED_GUIDANCE = "saved_guidance";

const LAST_CONVO_KEY = "last_farmer_conversation";
const LOCAL_STORAGE_CONVO_KEY = "farmsaathi_persisted_messages";
const LOCAL_STORAGE_GUIDANCE_KEY = "farmsaathi_saved_guidance_items";

/**
 * Open or upgrade the FarmSaathi IndexedDB database.
 */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !("indexedDB" in window)) {
      return reject(new Error("IndexedDB is not supported in this environment."));
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_CONVERSATION)) {
        db.createObjectStore(STORE_CONVERSATION, { keyPath: "key" });
      }
      if (!db.objectStoreNames.contains(STORE_SAVED_GUIDANCE)) {
        db.createObjectStore(STORE_SAVED_GUIDANCE, { keyPath: "id" });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Failed to open IndexedDB"));
  });
}

/**
 * Persist the current or last conversation into IndexedDB for offline restoration.
 * Strips bulky audio base64 binary strings to conserve browser quota.
 */
export async function saveLastConversation(
  messages: ChatMessage[],
  sessionId?: string | null,
  selectedLang?: SupportedLanguage
): Promise<void> {
  const sanitizedMessages = messages.map((m) => {
    const copy = { ...m };
    delete copy.audioBase64;
    return copy;
  });

  const record = {
    key: LAST_CONVO_KEY,
    messages: sanitizedMessages,
    sessionId: sessionId || null,
    selectedLang: selectedLang || "en",
    savedAt: new Date().toISOString(),
  };

  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_CONVERSATION, "readwrite");
      const store = tx.objectStore(STORE_CONVERSATION);
      const req = store.put(record);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn("[OfflineStorage] IndexedDB save failed, using localStorage fallback:", err);
    try {
      localStorage.setItem(LOCAL_STORAGE_CONVO_KEY, JSON.stringify(record));
    } catch {
      // LocalStorage quota exceeded or disabled
    }
  }
}

/**
 * Retrieve the last conversation from IndexedDB (or localStorage fallback).
 */
export async function getLastConversation(): Promise<{
  messages: ChatMessage[];
  sessionId?: string | null;
  selectedLang?: SupportedLanguage;
  savedAt: string;
} | null> {
  try {
    const db = await openDB();
    return await new Promise((resolve) => {
      const tx = db.transaction(STORE_CONVERSATION, "readonly");
      const store = tx.objectStore(STORE_CONVERSATION);
      const req = store.get(LAST_CONVO_KEY);
      req.onsuccess = () => {
        if (req.result && Array.isArray(req.result.messages)) {
          resolve(req.result);
        } else {
          resolve(null);
        }
      };
      req.onerror = () => resolve(null);
    });
  } catch {
    // Fallback to localStorage
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_CONVO_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.messages)) {
          return parsed;
        }
        if (Array.isArray(parsed)) {
          return {
            messages: parsed,
            sessionId: null,
            selectedLang: "en",
            savedAt: new Date().toISOString(),
          };
        }
      }
    } catch {
      // Storage unavailable
    }
    return null;
  }
}

/**
 * Clear the last stored conversation from IndexedDB and localStorage.
 */
export async function clearLastConversation(): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_CONVERSATION, "readwrite");
      const store = tx.objectStore(STORE_CONVERSATION);
      const req = store.delete(LAST_CONVO_KEY);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    // Fallback
  }

  try {
    localStorage.removeItem(LOCAL_STORAGE_CONVO_KEY);
    sessionStorage.removeItem("farmsaathi_messages");
  } catch {
    // Storage unavailable
  }
}

/**
 * Save an agricultural guidance record into the farmer's offline bookmarks.
 */
export async function saveGuidanceItem(item: SavedGuidanceItem): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_SAVED_GUIDANCE, "readwrite");
      const store = tx.objectStore(STORE_SAVED_GUIDANCE);
      const req = store.put(item);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.warn("[OfflineStorage] IndexedDB saveGuidance failed, using localStorage:", err);
    try {
      const existing = getSavedGuidanceFallback();
      const filtered = existing.filter((g) => g.id !== item.id);
      filtered.unshift(item);
      localStorage.setItem(LOCAL_STORAGE_GUIDANCE_KEY, JSON.stringify(filtered));
    } catch {
      // Quota exceeded
    }
  }
}

/**
 * List all saved offline agricultural guidance items for the farmer.
 */
export async function getSavedGuidanceList(): Promise<SavedGuidanceItem[]> {
  try {
    const db = await openDB();
    return await new Promise<SavedGuidanceItem[]>((resolve) => {
      const tx = db.transaction(STORE_SAVED_GUIDANCE, "readonly");
      const store = tx.objectStore(STORE_SAVED_GUIDANCE);
      const req = store.getAll();
      req.onsuccess = () => {
        const items: SavedGuidanceItem[] = req.result || [];
        items.sort((a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime());
        resolve(items);
      };
      req.onerror = () => resolve(getSavedGuidanceFallback());
    });
  } catch {
    return getSavedGuidanceFallback();
  }
}

/**
 * Remove a specific saved guidance record.
 */
export async function removeSavedGuidance(id: string): Promise<void> {
  try {
    const db = await openDB();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(STORE_SAVED_GUIDANCE, "readwrite");
      const store = tx.objectStore(STORE_SAVED_GUIDANCE);
      const req = store.delete(id);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch {
    // Fallback
  }

  try {
    const existing = getSavedGuidanceFallback();
    const updated = existing.filter((g) => g.id !== id);
    localStorage.setItem(LOCAL_STORAGE_GUIDANCE_KEY, JSON.stringify(updated));
  } catch {
    // Storage unavailable
  }
}

/**
 * Check if a specific guidance item is currently bookmarked offline.
 */
export async function isGuidanceSaved(id: string): Promise<boolean> {
  try {
    const db = await openDB();
    return await new Promise<boolean>((resolve) => {
      const tx = db.transaction(STORE_SAVED_GUIDANCE, "readonly");
      const store = tx.objectStore(STORE_SAVED_GUIDANCE);
      const req = store.get(id);
      req.onsuccess = () => resolve(Boolean(req.result));
      req.onerror = () => resolve(false);
    });
  } catch {
    const list = getSavedGuidanceFallback();
    return list.some((g) => g.id === id);
  }
}

function getSavedGuidanceFallback(): SavedGuidanceItem[] {
  try {
    const raw = localStorage.getItem(LOCAL_STORAGE_GUIDANCE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) return parsed;
    }
  } catch {
    // Storage unavailable
  }
  return [];
}
