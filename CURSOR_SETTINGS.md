# Cursor IDE Settings - File Deletion Protection

## ✅ What's Been Configured

### 1. File Deletion Protection (in `.vscode/settings.json`)
I've added these settings to prevent accidental file deletions:
```json
"cursor.agent.fileDeletionProtection": true,
"cursor.agent.confirmFileDeletion": true,
```

### 2. Monorepo Scaffolding Disabled
Prevents the auto-opening scaffolding chat that was interfering:
```json
"cursor.aiScaffold.enabled": false,
"cursor.monorepoScaffold.enabled": false,
"cursor.chat.autoOpen": false,
"cursor.chat.autoOpenOnMonorepo": false,
```

## 🔧 How to Enable File Deletion Protection in Cursor UI

If the settings file doesn't work, you can enable it manually:

1. **Open Cursor Settings:**
   - Press `Ctrl+,` (or `Cmd+,` on Mac)
   - Or go to File → Preferences → Settings

2. **Search for "deletion" or "agent":**
   - Look for settings like:
     - "Cursor: Agent File Deletion Protection"
     - "Cursor: Confirm File Deletion"
     - "Agent: File Deletion Protection"

3. **Enable the protection:**
   - Check the box for file deletion protection
   - Set confirmation to "always" or "ask"

4. **Alternative Method - Settings JSON:**
   - Press `Ctrl+Shift+P` → "Preferences: Open User Settings (JSON)"
   - Add these lines:
   ```json
   {
     "cursor.agent.fileDeletionProtection": true,
     "cursor.agent.confirmFileDeletion": true
   }
   ```

## 🔄 Reload Cursor

After making changes, reload Cursor:
- `Ctrl+Shift+P` → "Developer: Reload Window"

## ✅ Verification

To verify it's working:
1. Ask the AI to delete a test file
2. You should see a confirmation prompt
3. The AI should ask before deleting

## 📝 Note

Cursor's settings may vary by version. If these exact setting names don't work:
- Check Cursor's documentation
- Look in Settings UI for similar options
- The protection may be enabled by default in newer versions

