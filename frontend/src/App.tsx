import { Button } from "./components/ui/button";
import { Mail } from "lucide-react";

export default function App() {
  return (
    <main className="min-h-screen p-8">
      <h1>Locus</h1>
      <Button>
        <Mail className="mr-2 h-4 w-4" /> Login
      </Button>
    </main>
  );
}