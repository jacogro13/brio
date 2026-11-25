import { useCallback, useEffect, useState } from "react";
import { AuthPage } from "./components/AuthPage";
import { ChatThread } from "./components/ChatThread";
import { ConversationList } from "./components/ConversationList";
import { ConversationSettings } from "./components/ConversationSettings";
import { ErrorBanner } from "./components/ErrorBanner";
import { Greeting } from "./components/Greeting";
import { MessageInput } from "./components/MessageInput";
import { SidebarDrawer } from "./components/SidebarDrawer";
import { TopBar } from "./components/TopBar";
import { useActiveConversation } from "./hooks/useActiveConversation";
import { currentUsername, isSignedIn, logout } from "./hooks/useAuth";
import { useChatStream } from "./hooks/useChatStream";
import {
  useConversation,
  useConversationList,
  useDeleteConversation,
  useRenameConversation,
  useUpdateSettings,
  type ConversationSettings as Settings,
} from "./hooks/useConversations";
import { useMobileLayout } from "./hooks/useMobileLayout";
import { useProfile } from "./hooks/useProfile";
import { useLanguage } from "./i18n";

export default function App() {
  const [authed, setAuthed] = useState(isSignedIn);

  if (!authed) {
    return <AuthPage onAuthenticated={() => setAuthed(true)} />;
  }
  return <ChatApp />;
}

function ChatApp() {
  const { t, syncLanguage } = useLanguage();
  const list = useConversationList();
  const conversations = list.data ?? [];
  const { mutateAsync: deleteConversation } = useDeleteConversation();
  const { mutateAsync: renameConversation } = useRenameConversation();
  const { mutateAsync: updateSettings } = useUpdateSettings();
  const profile = useProfile().data;
  const { activeId, threadKey, select, startNew, forget, ensureConversation } =
    useActiveConversation();
  // Undefined for a draft (activeId === null).
  const open = useConversation(activeId).data;
  const { mobile, sidebarOpen, setSidebarOpen, closeSidebarOnMobile } = useMobileLayout();

  // The banner shows one error: the latest failed action, else a list that
  // never loaded. A failed refetch of a list already on screen stays silent; a
  // dismissed list error stays hidden until the list fails again.
  const [actionError, setActionError] = useState<unknown>(null);
  const [dismissedListErrorAt, setDismissedListErrorAt] = useState(0);
  const report = useCallback((error: unknown) => setActionError(error), []);
  const listError =
    list.data === undefined && list.isError && list.errorUpdatedAt !== dismissedListErrorAt
      ? list.error
      : null;
  const bannerError = actionError ?? listError;
  const dismissBanner = () => {
    setActionError(null);
    setDismissedListErrorAt(list.errorUpdatedAt);
  };

  const {
    streaming,
    streamingThinking,
    streamingToolEvents,
    isStreaming,
    streamError,
    send,
    regenerate,
    edit,
    stop,
  } = useChatStream({ activeId, ensureConversation, onError: report });

  // Seed the language from the server profile (source of truth across devices),
  // overriding the localStorage/browser guess made before auth.
  useEffect(() => {
    if (profile) syncLanguage(profile.language);
  }, [profile, syncLanguage]);

  const username = currentUsername();

  // On failure the open chat stays as it was and the banner says why.
  const handleSelect = async (id: string) => {
    try {
      await select(id);
      closeSidebarOnMobile();
    } catch (error) {
      report(error);
    }
  };

  // No POST here — start a fresh draft; the row is created on first send/upload.
  const handleNew = () => {
    startNew();
    closeSidebarOnMobile();
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteConversation(id);
      forget(id);
    } catch (error) {
      report(error);
    }
  };

  const handleRename = (id: string, title: string) =>
    renameConversation({ id, title }).catch(report);

  const handleUpdateSettings = (settings: Settings) => {
    if (activeId === null) return;
    updateSettings({ id: activeId, settings }).catch(report);
  };

  return (
    <div
      className="app-shell"
      style={{
        display: "flex",
        flexDirection: "column",
        background: "var(--bg)",
        color: "var(--text)",
        fontFamily: "var(--font-sans)",
      }}
    >
      <TopBar
        title={open?.title ?? t("appName")}
        settings={
          open && (
            <ConversationSettings
              key={open.id}
              conversation={open}
              onUpdate={handleUpdateSettings}
            />
          )
        }
        username={username}
        mobile={mobile}
        onToggleSidebar={() => setSidebarOpen((o) => !o)}
        onLogout={logout}
      />

      {/* Body */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
        <SidebarDrawer open={sidebarOpen} mobile={mobile} onClose={() => setSidebarOpen(false)}>
          <ConversationList
            conversations={conversations}
            activeId={activeId}
            onSelect={handleSelect}
            onNew={handleNew}
            onDelete={handleDelete}
            onRename={handleRename}
          />
        </SidebarDrawer>

        {/* Chat area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {bannerError != null && <ErrorBanner error={bannerError} onDismiss={dismissBanner} />}
          {!open || open.messages.length === 0 ? (
            <Greeting />
          ) : (
            <ChatThread
              conversationId={open.id}
              messages={open.messages}
              streamingContent={streaming}
              streamingThinking={streamingThinking}
              streamingToolEvents={streamingToolEvents}
              isStreaming={isStreaming}
              onEdit={edit}
              onRetry={regenerate}
              onDownloadError={report}
              streamError={streamError}
            />
          )}
          <MessageInput
            key={threadKey}
            conversationId={activeId}
            onSend={send}
            onStop={stop}
            isStreaming={isStreaming}
            ensureConversation={ensureConversation}
          />
        </div>
      </div>
    </div>
  );
}
