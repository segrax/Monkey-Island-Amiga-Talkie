/* GPL-3.0-or-later. Included after the AmigaDOS/Workbench declarations. */
static int launch_workbench(struct WBStartup *wb) {
	BPTR previous, console;
	LONG started;
	char answer[8];
	const char *message;
	if (!wb || wb->sm_NumArgs < 1 || !wb->sm_ArgList ||
	    !wb->sm_ArgList[0].wa_Lock)
		return 20;
	previous = CurrentDir(wb->sm_ArgList[0].wa_Lock);
	/* Plain CON: syntax works on Kickstart 1.3 too. */
	console = Open("CON:0/20/640/160/Monkey Island Talkie", MODE_NEWFILE);
	if (!console) {
		CurrentDir(previous);
		return 20;
	}
	/* The original game selects CLI vs WB startup using pr_CLI. Entering
	 * it in this WB process would wait for a startup message already consumed
	 * by our C runtime. Execute creates the CLI context it needs. */
	started = Execute("Stack 65536\nMonkeyTalkie\n", 0, console);
	message = started ? "\nPress Return to close this window.\n" :
		"\nCannot start the game Shell. Check C:Run is available on Kickstart 1.3.\n"
		"Press Return to close this window.\n";
	Write(console, (APTR)message, (LONG)strlen(message));
	Read(console, answer, sizeof(answer));
	Close(console);
	CurrentDir(previous);
	/* Execute reports Shell startup success, not the game's return code. */
	return started ? 0 : 20;
}
