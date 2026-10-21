# Spoken test clips for the formatting pipeline (Windows TTS, 16 kHz mono) -> data\fmt_*.wav + data\fmt_*.txt (what was said)
# runon_* reproduce the real defect: long speech with no pauses, which Whisper tends to return without punctuation.
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$clips = [ordered]@{
  "runon_work"  = "so today i worked on the project and i fixed the microphone bug then i tested the app in notepad and it worked fine but the punctuation was missing so i need to fix that next and after that i want to add the mascot to the bottom of the screen"
  "runon_plan"  = "okay so the plan for tomorrow is to finish the formatting code and write the tests then we can package the app and send it to the team for feedback i think it should take about two days"
  "pauses"      = "I tested the new build this morning. It starts quickly. The only problem is the settings page, which still looks unfinished."
  "list"        = "First point improve the UI second point fix the microphone third point add number formatting"
  "bullets"     = "Bullet point improve the design bullet point fix recording errors"
  "numbers"     = "The price went up by fifteen percent to three point five million dollars on October twenty first"
  "commands"    = "Dear team new paragraph the release is ready new line thanks for your help"
}
$root = Split-Path -Parent $PSScriptRoot
foreach ($k in $clips.Keys) {
  foreach ($rate in 0, 2) {
    $name = if ($rate -eq 0) { $k } else { "${k}_fast" }
    if ($rate -ne 0 -and -not $k.StartsWith("runon")) { continue }
    $s.Rate = $rate
    $s.SetOutputToWaveFile((Join-Path $root "data\fmt_$name.wav"), $fmt)
    $s.Speak($clips[$k]); $s.SetOutputToNull()
    Set-Content -Path (Join-Path $root "data\fmt_$name.txt") -Value $clips[$k] -Encoding UTF8
  }
}
# Real pauses between sentences but no punctuation in the script: can pause timing restore sentence breaks?
$said = "so today i worked on the project", "i fixed the microphone bug and then i tested the app in notepad", "it worked fine but the punctuation was missing", "next i want to add the mascot"
$ssml = '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">' + ($said -join ' <break time="800ms"/> ') + '</speak>'
$s.Rate = 0
$s.SetOutputToWaveFile((Join-Path $root "data\fmt_pausedrunon.wav"), $fmt)
$s.SpeakSsml($ssml); $s.SetOutputToNull()
Set-Content -Path (Join-Path $root "data\fmt_pausedrunon.txt") -Value (($said | ForEach-Object { $_.Substring(0,1).ToUpper() + $_.Substring(1) }) -join ". ") -Encoding UTF8
Write-Host "made format clips"
