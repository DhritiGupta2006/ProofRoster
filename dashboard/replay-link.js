// A specific saved run can be reviewed through a shareable localhost URL.
(async()=>{
  const filename=new URLSearchParams(location.search).get('replay');
  if(!filename)return;
  try{
    const response=await fetch('/api/replays/'+encodeURIComponent(filename));
    if(!response.ok)throw new Error('Saved replay not found');
    const data=await response.json();
    await selectScenario(data.scenario);
    $('mode').value='replay';render(data);
  }catch(error){banner(error.message,'error')}
})();
