<script lang="ts">
	import { getContext } from 'svelte';

	import Select from '$lib/components/common/Select.svelte';
	import Check from '$lib/components/icons/Check.svelte';
	import ChatBubble from '$lib/components/icons/ChatBubble.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import XMark from '$lib/components/icons/XMark.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';

	import { getChatListBySearchText } from '$lib/apis/chats';

	const i18n = getContext('i18n');

	export let target_chat_id = '';
	export let side: 'top' | 'bottom' = 'top';
	export let align: 'start' | 'end' = 'start';
	export let onChange: () => void = () => {};

	let chatSearch = '';
	let localChats: Record<string, unknown>[] = [];
	let loading = false;
	let hasMore = true;
	let page = 1;
	let activeQuery = '';
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let selectedChatTitle = '';

	const PAGE_SIZE = 60;
	const MAX_PAGES = 10;

	const fetchChats = async (query: string, pageNum: number = 1, append = false) => {
		if (loading || (!append && page > pageNum)) return;
		loading = true;
		try {
			const token = localStorage.token || '';
			const fetched = await getChatListBySearchText(token, query, pageNum).catch(() => []);
			if (append) {
				localChats = [...localChats, ...(fetched ?? [])];
			} else {
				localChats = fetched ?? [];
			}
			page = pageNum;
			hasMore = (fetched?.length ?? 0) === PAGE_SIZE && pageNum < MAX_PAGES;
			activeQuery = query;

			if (!append && target_chat_id) {
				const match = localChats.find((chat) => chat?.id === target_chat_id);
				if (match) selectedChatTitle = String(match.title || '');
			}
		} finally {
			loading = false;
		}
	};

	const loadInitialChats = () => {
		page = 0;
		hasMore = true;
		localChats = [];
		fetchChats('', 1);
	};

	function handleScroll(e: Event) {
		const target = e.target as HTMLElement;
		if (target.scrollTop + target.clientHeight >= target.scrollHeight - 50 && hasMore && !loading) {
			fetchChats(activeQuery, page + 1, true);
		}
	}

	const handleOpen = () => {
		loadInitialChats();
	};

	function handleSearch() {
		if (debounceTimer) clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			page = 0;
			hasMore = true;
			fetchChats(chatSearch.trim(), 1);
		}, 300);
	}

	const handleContentReady = (el: HTMLElement) => {
		el.addEventListener('scroll', handleScroll);
	};

	$: selectedChat = localChats.find((chat) => chat?.id === target_chat_id);
	$: chatLabel = selectedChat ? selectedChat.title : (selectedChatTitle || $i18n.t('Select a chat'));

	function truncate(str: string | undefined, len = 40) {
		return str && str.length > len ? str.slice(0, len) + '…' : str;
	}
</script>

<Select
	bind:value={target_chat_id}
	items={localChats.map((chat) => ({ value: chat.id, label: chat.title }))}
	placeholder={$i18n.t('Select a chat')}
	{align}
	{side}
	onOpen={() => handleOpen()}
	onContentReady={handleContentReady}
	triggerClass="relative h-8 max-w-[11rem] flex items-center gap-1.5 px-2.5 py-1.5 bg-transparent rounded-2xl text-xs font-normal text-gray-600 transition hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
	contentClass="w-72 shadow-lg"
	maxHeight="18rem"
	onChange={() => onChange()}
	onClose={() => {
		chatSearch = '';
	}}
>
	<svelte:fragment slot="trigger">
		<ChatBubble className="size-3.5 shrink-0" />
		<div class="inline-flex h-input min-w-0 flex-1 truncate bg-transparent outline-hidden">
			{chatLabel}
		</div>

		{#if target_chat_id}
			<button
				class="outline-none"
				type="button"
				on:click|stopPropagation={() => {
					target_chat_id = '';
					selectedChatTitle = '';
					chatSearch = '';
					onChange();
				}}
				aria-label={$i18n.t('Clear')}
			>
				<XMark className="size-3.5" />
			</button>
		{:else}
			<ChevronDown className="size-2.5 shrink-0" strokeWidth="2.5" />
		{/if}
	</svelte:fragment>

	<svelte:fragment let:selectItem>
		<div class="flex items-center gap-1.5 px-2 py-1">
			<Search className="size-3.5 shrink-0" strokeWidth="2.5" />
			<input
				bind:value={chatSearch}
				class="w-full bg-transparent text-[13px] outline-hidden"
				placeholder={$i18n.t('Search chats')}
				autocomplete="off"
				on:click|stopPropagation
				on:input={() => handleSearch()}
			/>
		</div>

		{#if localChats.length > 0}
			<hr class="mx-1 my-0.5 border-gray-50/30 dark:border-gray-800/30" />
			<div class="px-2 py-1 text-[11px] text-gray-500 dark:text-gray-400">
				{$i18n.t('Chats')}
			</div>
		{/if}

		{#each localChats as chat (chat.id)}
			<button
				type="button"
				class="flex h-[1.6875rem] w-full cursor-pointer items-center justify-between gap-2 rounded-xl bg-transparent px-2 text-[13px] hover:bg-gray-50/40 hover:text-gray-900 dark:hover:bg-gray-800/40 dark:hover:text-gray-100 {target_chat_id ===
				chat.id
					? 'text-gray-900 dark:text-gray-100'
					: 'text-gray-700 dark:text-gray-300'}"
				on:click={() => {
					const isSelected = target_chat_id === chat.id;
					target_chat_id = isSelected ? '' : String(chat.id);
					selectedChatTitle = isSelected ? '' : String(chat.title);
					selectItem({
						value: target_chat_id,
						label: isSelected ? $i18n.t('Select a chat') : String(chat.title)
					});
					onChange();
					chatSearch = '';
				}}
			>
				<div class="flex min-w-0 items-center gap-1.5">
					<ChatBubble className="size-3.5 shrink-0" />
					<span class="min-w-0 truncate">{truncate(chat.title)}</span>
				</div>
				{#if target_chat_id === chat.id}
					<Check className="size-3.5 shrink-0" strokeWidth="2" />
				{/if}
			</button>
		{:else}
			{#if !loading}
				<div class="px-2 py-1 text-[11px] text-gray-500 dark:text-gray-400">
					{$i18n.t('No chats')}
				</div>
			{/if}
		{/each}

		{#if loading && localChats.length > 0}
			<div class="flex justify-center py-2">
				<svg class="size-3.5 animate-spin text-gray-400" viewBox="0 0 24 24" fill="none">
					<circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
					<path
						class="opacity-75"
						fill="currentColor"
						d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
					/>
				</svg>
			</div>
		{/if}

		{#if !hasMore && localChats.length > 0}
			<div class="px-2 py-1 text-[11px] text-gray-400 dark:text-gray-500">
				{$i18n.t('End of results')}
			</div>
		{/if}
	</svelte:fragment>
</Select>
