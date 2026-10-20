# Spoken test clips for Smart mode (Windows TTS, 16 kHz mono) -> data\smart_*.wav
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$s.Rate = 0
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$clips = [ordered]@{
  "coffee"   = "Let's do coffee at two. Actually, three."
  "scratch"  = "Schedule the review for Monday. No, scratch that. Tuesday."
  "points"   = "Here are the steps. One, open the laptop. Two, log in. Three, open the dashboard. Four, check the sales numbers. Five, export the report. Six, email it to the team. Seven, buy milk. No, no, that is not the seventh point. The seventh point is archive the old files."
  "punct"    = "Hello comma how are you question mark"
  "question" = "What is the capital of France"
  "plain"    = "The quarterly numbers look good and we should share them with the board next week."
}
$root = Split-Path -Parent $PSScriptRoot
foreach ($k in $clips.Keys) {
  $s.SetOutputToWaveFile((Join-Path $root "data\smart_$k.wav"), $fmt)
  $s.Speak($clips[$k]); $s.SetOutputToNull()
}
Write-Host "made $($clips.Count) clips"
