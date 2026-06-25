property appName : "LogicX-Push2 Launcher"
property appVersion : "1.2.0"
property githubRepo : "zurie/LogicX-Push2"
property configDir : ""
property configFile : ""
property push2PID : ""

on run
	set configDir to POSIX path of (path to library folder from user domain) & "Application Support/LogicX-Push2 Launcher/"
	set configFile to configDir & "repo-path.txt"
	
	my ensureConfigDir()
	
	set repoPath to my getSavedRepoPath()
	
	if repoPath is "" then
		set repoPath to my chooseRepoPath()
		my saveRepoPath(repoPath)
	end if
	
	my silentUpdateCheck()
	
	repeat
		try
			set userChoice to button returned of (display dialog appName & " v" & appVersion & return & return & "Repo: " & repoPath buttons {"Setup...", "Run", "Quit"} default button "Run" cancel button "Quit")
		on error number -128
			quit
			return
		end try
		
		if userChoice is "Setup..." then
			my showSetupMenu(repoPath)
			set repoPath to my getSavedRepoPath()
			if repoPath is "" then
				set repoPath to my chooseRepoPath()
				my saveRepoPath(repoPath)
			end if
			
		else if userChoice is "Run" then
			my runPush2(repoPath)
			
			try
				set runningChoice to button returned of (display dialog "LogicX-Push2 is running." & return & return & "PID: " & push2PID & return & "Log: /tmp/logicx-push2.log" buttons {"Setup...", "Stop Push2", "Quit App"} default button "Stop Push2")
			on error number -128
				my quitPush2()
				quit
				return
			end try
			
			if runningChoice is "Stop Push2" then
				my quitPush2()
				
			else if runningChoice is "Setup..." then
				my quitPush2()
				my showSetupMenu(repoPath)
				set repoPath to my getSavedRepoPath()
				if repoPath is "" then
					set repoPath to my chooseRepoPath()
					my saveRepoPath(repoPath)
				end if
				
			else if runningChoice is "Quit App" then
				my quitPush2()
				quit
			end if
		end if
	end repeat
end run

on showSetupMenu(repoPath)
	try
		set setupChoice to button returned of (display dialog "Setup � " & appName & return & return & "Repo: " & repoPath buttons {"Install Deps", "Change Path", "Check Updates"} default button "Install Deps")
	on error number -128
		return
	end try
	
	if setupChoice is "Install Deps" then
		my runInstaller(repoPath)
		
	else if setupChoice is "Change Path" then
		set newPath to my chooseRepoPath()
		my saveRepoPath(newPath)
		
	else if setupChoice is "Check Updates" then
		my checkForUpdates(true)
	end if
end showSetupMenu

on runInstaller(repoPath)
	set installScript to repoPath & "install.sh"
	try
		do shell script "test -f " & quoted form of installScript
	on error
		display dialog "install.sh not found in the repo folder." & return & return & "Please pull the latest changes from GitHub." buttons {"OK"} default button "OK"
		return
	end try
	
	do shell script "chmod +x " & quoted form of installScript
	tell application "Terminal"
		activate
		do script "cd " & quoted form of repoPath & " && ./install.sh"
	end tell
end runInstaller

on silentUpdateCheck()
	try
		set latestTag to my getLatestVersion()
		if latestTag is "" then return
		
		set needsUpdate to do shell script "python3 -c \"
v1=tuple(int(x) for x in '" & appVersion & "'.split('.'))
v2=tuple(int(x) for x in '" & latestTag & "'.split('.'))
print('yes' if v2>v1 else 'no')
\""
		if needsUpdate is "yes" then
			my offerUpdate(latestTag)
		end if
	end try
end silentUpdateCheck

on checkForUpdates(interactive)
	try
		set latestTag to my getLatestVersion()
		
		if latestTag is "" then
			if interactive then
				display dialog "Could not check for updates." & return & "Please check your internet connection." buttons {"OK"} default button "OK"
			end if
			return
		end if
		
		set needsUpdate to do shell script "python3 -c \"
v1=tuple(int(x) for x in '" & appVersion & "'.split('.'))
v2=tuple(int(x) for x in '" & latestTag & "'.split('.'))
print('yes' if v2>v1 else 'no')
\""
		
		if needsUpdate is "yes" then
			my offerUpdate(latestTag)
		else if interactive then
			display dialog "You're up to date!" & return & return & "Current: v" & appVersion & return & "Latest: v" & latestTag buttons {"OK"} default button "OK"
		end if
	on error errMsg
		if interactive then
			display dialog "Update check failed:" & return & errMsg buttons {"OK"} default button "OK"
		end if
	end try
end checkForUpdates

on getLatestVersion()
	try
		set latestTag to do shell script "curl -sf --max-time 8 'https://api.github.com/repos/" & githubRepo & "/releases/latest' | python3 -c \"import sys,json; print(json.load(sys.stdin).get('tag_name','').lstrip('v'))\" 2>/dev/null || echo ''"
		return latestTag
	on error
		return ""
	end try
end getLatestVersion

on offerUpdate(newVersion)
	set updateChoice to button returned of (display dialog "Update available!" & return & return & "Current: v" & appVersion & return & "New:     v" & newVersion & return & return & "Download and install now?" buttons {"Later", "Update Now"} default button "Update Now")
	if updateChoice is "Update Now" then
		my performUpdate(newVersion)
	end if
end offerUpdate

on performUpdate(newVersion)
	set tmpZip to "/tmp/push2_update.zip"
	set tmpDir to "/tmp/push2_update"
	set downloadURL to "https://github.com/" & githubRepo & "/releases/download/v" & newVersion & "/Push2.app.zip"
	
	set appBundlePath to POSIX path of (path to me)
	if appBundlePath ends with "/" then
		set appBundlePath to text 1 thru -2 of appBundlePath
	end if
	
	my quitPush2()
	
	try
		display dialog "Downloading v" & newVersion & "..." buttons {"OK"} default button "OK" giving up after 2
		
		do shell script "curl -L --max-time 120 -o " & quoted form of tmpZip & " " & quoted form of downloadURL
		-- ditto (not unzip): restores the custom-icon resource fork + FinderInfo bit
		do shell script "rm -rf " & quoted form of tmpDir & " && mkdir -p " & quoted form of tmpDir & " && ditto -x -k " & quoted form of tmpZip & " " & quoted form of tmpDir
		do shell script "test -d " & quoted form of (tmpDir & "/Push2.app")
		
		-- Backup then replace
		do shell script "rm -rf " & quoted form of (appBundlePath & ".backup") & " && cp -R " & quoted form of appBundlePath & " " & quoted form of (appBundlePath & ".backup")
		do shell script "cp -Rf " & quoted form of (tmpDir & "/Push2.app/") & " " & quoted form of appBundlePath & "/"

		-- Re-apply the custom Finder icon: the kHasCustomIcon FinderInfo bit is
		-- not carried inside a zip, so it must be re-set on this machine.
		try
			do shell script "test -x " & quoted form of (appBundlePath & "/Contents/Resources/apply_icon.sh") & " && " & quoted form of (appBundlePath & "/Contents/Resources/apply_icon.sh") & " " & quoted form of appBundlePath
		end try
		
		do shell script "rm -rf " & quoted form of tmpDir & " " & quoted form of tmpZip
		
		-- Relaunch updated app
		do shell script "sleep 1 && open " & quoted form of appBundlePath & " &"
		
		display dialog "Updated to v" & newVersion & "!" & return & "Relaunching..." buttons {"OK"} default button "OK" giving up after 3
		quit
		
	on error errMsg
		-- Attempt to restore backup
		try
			do shell script "test -d " & quoted form of (appBundlePath & ".backup") & " && cp -Rf " & quoted form of (appBundlePath & ".backup") & "/ " & quoted form of appBundlePath & "/"
		end try
		do shell script "rm -rf " & quoted form of tmpDir & " " & quoted form of tmpZip & " 2>/dev/null || true"
		
		display dialog "Update failed:" & return & errMsg & return & return & "Download manually:" & return & "github.com/" & githubRepo & "/releases" buttons {"OK"} default button "OK"
	end try
end performUpdate

on runPush2(repoPath)
	set launchCommand to "
cd " & quoted form of repoPath & " || exit 1
chmod +x ./run.sh
./run.sh > /tmp/logicx-push2.log 2>&1 &
echo $!
"
	set push2PID to do shell script launchCommand
end runPush2

on quitPush2()
	if push2PID is not "" then
		try
			do shell script "kill " & push2PID & " 2>/dev/null || true"
		end try
		delay 1
		try
			do shell script "kill -9 " & push2PID & " 2>/dev/null || true"
		end try
		set push2PID to ""
	end if
end quitPush2

on chooseRepoPath()
	set repoFolder to choose folder with prompt "Choose your LogicX-Push2 repo folder:"
	set repoPath to POSIX path of repoFolder
	try
		do shell script "test -f " & quoted form of (repoPath & "run.sh")
	on error
		display dialog "That folder does not contain run.sh." & return & return & "Please choose the LogicX-Push2 repo root folder." buttons {"Choose Again"} default button "Choose Again"
		return my chooseRepoPath()
	end try
	return repoPath
end chooseRepoPath

on getSavedRepoPath()
	try
		set savedPath to do shell script "cat " & quoted form of configFile
		if savedPath is not "" then
			try
				do shell script "test -d " & quoted form of savedPath & " && test -f " & quoted form of (savedPath & "run.sh")
				return savedPath
			end try
		end if
	end try
	return ""
end getSavedRepoPath

on saveRepoPath(repoPath)
	my ensureConfigDir()
	do shell script "printf %s " & quoted form of repoPath & " > " & quoted form of configFile
end saveRepoPath

on ensureConfigDir()
	do shell script "mkdir -p " & quoted form of configDir
end ensureConfigDir

on quit
	my quitPush2()
	continue quit
end quit
