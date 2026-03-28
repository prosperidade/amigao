import * as SQLite from 'expo-sqlite';

let db: SQLite.SQLiteDatabase | null = null;

export const initDb = async () => {
  if (db) return db;

  try {
    db = await SQLite.openDatabaseAsync('amigao_offline.db');

    // Enable Foreign Keys and WAL mode for better concurrency
    await db.execAsync(`
      PRAGMA journal_mode = WAL;
      PRAGMA foreign_keys = ON;
      
      -- Tabela Local de Processos
      CREATE TABLE IF NOT EXISTS processes (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER NOT NULL,
        client_id INTEGER,
        property_id INTEGER,
        name TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        priority TEXT,
        urgency TEXT,
        due_date TEXT,
        created_at TEXT
      );

      -- Tabela Local de Tarefas / Checklists
      CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY,
        tenant_id INTEGER NOT NULL,
        process_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        due_date TEXT,
        is_synced BOOLEAN DEFAULT 1,
        FOREIGN KEY (process_id) REFERENCES processes (id) ON DELETE CASCADE
      );

      -- Fila de Sincronização Automática (Upload Background)
      -- Serve para guardar ações feitas offline (Ex: Completar Task, Subir Foto)
      CREATE TABLE IF NOT EXISTS sync_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        endpoint TEXT NOT NULL,
        method TEXT NOT NULL, -- POST, PUT, PATCH
        payload TEXT NOT NULL, -- JSON String
        status TEXT DEFAULT 'pending', -- pending, error, synced
        error_message TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
      );
    `);

    console.log('[SQLite] Local database initialized successfully');
    return db;
  } catch (err: any) {
    console.error('[SQLite] Error initializing database: ', err.message);
    throw err;
  }
};

export const getDb = () => {
  if (!db) {
    throw new Error('[SQLite] Database not initialized. Call initDb() first.');
  }
  return db;
};
