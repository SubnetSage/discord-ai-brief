import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import { Loader2, PlayCircle, Calendar, Link as LinkIcon } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";

const Index = () => {
  const { toast } = useToast();
  const [isRunning, setIsRunning] = useState(false);
  const [lastRun, setLastRun] = useState<{
    linkCount: number;
    articleCount: number;
    timestamp: string;
  } | null>(null);

  const runSummary = async () => {
    setIsRunning(true);
    
    try {
      toast({
        title: "Starting summary generation",
        description: "Scanning Discord channels for today's links...",
      });

      const { data, error } = await supabase.functions.invoke('daily-ai-summary', {
        body: {}
      });

      if (error) throw error;

      setLastRun({
        linkCount: data.linkCount || 0,
        articleCount: data.articleCount || 0,
        timestamp: new Date().toISOString(),
      });

      toast({
        title: "✅ Summary generated!",
        description: `Processed ${data.linkCount} links and posted to Discord`,
      });

    } catch (error) {
      console.error('Error running summary:', error);
      toast({
        title: "❌ Error",
        description: error instanceof Error ? error.message : "Failed to generate summary",
        variant: "destructive",
      });
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-background via-background to-muted p-8">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="text-center space-y-4">
          <h1 className="text-5xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
            Discord AI Daily
          </h1>
          <p className="text-muted-foreground text-lg">
            Automated AI news summarization from Discord channels
          </p>
        </header>

        <Card className="border-2 shadow-lg">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <PlayCircle className="h-6 w-6" />
              Generate Summary
            </CardTitle>
            <CardDescription>
              Scan configured Discord channels for today's AI news and generate a summary
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <Button
              onClick={runSummary}
              disabled={isRunning}
              size="lg"
              className="w-full"
            >
              {isRunning ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Generating Summary...
                </>
              ) : (
                <>
                  <PlayCircle className="mr-2 h-5 w-5" />
                  Run Summary Now
                </>
              )}
            </Button>

            {lastRun && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t">
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <Calendar className="h-4 w-4" />
                    Last Run
                  </p>
                  <p className="text-lg font-semibold">
                    {new Date(lastRun.timestamp).toLocaleString()}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <LinkIcon className="h-4 w-4" />
                    Links Found
                  </p>
                  <p className="text-lg font-semibold">
                    {lastRun.linkCount}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground flex items-center gap-2">
                    <LinkIcon className="h-4 w-4" />
                    Articles Scraped
                  </p>
                  <p className="text-lg font-semibold">
                    {lastRun.articleCount}
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Configuration</CardTitle>
            <CardDescription>
              Environment variables are configured in Lovable Cloud
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4">
              <div className="space-y-1">
                <p className="text-sm font-medium">Discord Token</p>
                <p className="text-sm text-muted-foreground">✓ Configured</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Summary Channel</p>
                <p className="text-sm text-muted-foreground">✓ Configured</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">Monitored Channels</p>
                <p className="text-sm text-muted-foreground">✓ Configured</p>
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium">AI Model</p>
                <p className="text-sm text-muted-foreground">Lovable AI (Google Gemini 2.5 Flash)</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-muted/50">
          <CardHeader>
            <CardTitle>About</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <p>
              This app automatically scans your configured Discord channels for messages from today (America/Chicago timezone),
              extracts all URLs, fetches article content, and generates a comprehensive AI-powered summary.
            </p>
            <p>
              The summary is posted to your designated Discord channel and includes:
            </p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>TL;DR highlights</li>
              <li>Notable product launches & updates</li>
              <li>Research papers & technical content</li>
              <li>Funding & policy news</li>
              <li>Complete link directory with summaries</li>
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Index;
